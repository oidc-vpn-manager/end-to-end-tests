"""End-to-end tests that exercise the project's CLI tools inside fresh Linux distro containers.

Each test launches a clean Ubuntu LTS or Alma Linux container on the same Docker
network as the e2e stack, installs only the tool's declared dependencies, and
runs the tool against the live services. The aim is to catch packaging,
dependency, and runtime issues the host-based tests miss.

Container distros are configurable via environment variables:

    UBUNTU_IMAGE  default: ubuntu:24.04
    ALMA_IMAGE    default: almalinux:10
    OIDC_USER_TYPE  default: it  (which tiny-oidc "Login as" button to click for test 4)

The compose stack must be running before these tests execute. Network name is
the explicit ``oidc-vpn-manager-tests`` defined in tests/docker-compose.yml.
"""
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization


COMPOSE_NETWORK = "oidc-vpn-manager-tests"
UBUNTU_IMAGE = os.environ.get("UBUNTU_IMAGE", "ubuntu:24.04")
ALMA_IMAGE = os.environ.get("ALMA_IMAGE", "almalinux:10")
OIDC_USER_TYPE = os.environ.get("OIDC_USER_TYPE", "it")
DEFAULT_TIMEOUT = 900  # apt/dnf + pip + (optionally) playwright install is slow


def _docker_run(image, mounts, command, timeout=DEFAULT_TIMEOUT, env=None):
    """Run a one-shot container on the e2e compose network.

    Always exposes ``HOST_UID`` and ``HOST_GID`` so scripts that must run as
    root inside the container can ``chown`` bind-mounted output back to the
    host user before exit. Without this, files written under restrictive
    modes (e.g. encrypted CA keys at 0600) become unreadable to the test
    runner and cause downstream pytest cleanup failures.
    """
    args = ["docker", "run", "--rm", "--network", COMPOSE_NETWORK]
    for src, dst, mode in mounts:
        args.extend(["-v", f"{src}:{dst}:{mode}"])
    merged_env = {"HOST_UID": str(os.getuid()), "HOST_GID": str(os.getgid())}
    merged_env.update(env or {})
    for k, v in merged_env.items():
        args.extend(["-e", f"{k}={v}"])
    args.extend([image, "bash", "-c", command])
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


# Leading snippet prepended to every container shell script: install an EXIT
# trap so anything written under /work is chowned back to the host user before
# the container exits, even when the main script fails. Otherwise files such
# as the encrypted CA key (mode 0600 owned by root) cannot be read by pytest.
_CHOWN_TRAP = (
    'trap \'chown -R "$HOST_UID:$HOST_GID" /work 2>/dev/null || true\' EXIT ; '
)


def _create_psk(psk_type: str, description: str) -> str:
    """Create a PSK via the frontend dev CLI and return the secret."""
    cmd = (
        f"docker exec tests-frontend-1 flask dev:create-psk "
        f"--description {shlex.quote(description)} "
        f"--template-set Default --psk-type {psk_type}"
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, f"PSK creation failed ({psk_type}): {result.stderr}\n{result.stdout}"
    for line in result.stdout.splitlines():
        if "PSK:" in line:
            return line.split("PSK:", 1)[1].strip()
    raise AssertionError(f"Could not parse PSK from output:\n{result.stdout}")


def _distro_kind(image: str) -> str:
    name = image.lower()
    if "ubuntu" in name:
        return "ubuntu"
    if "alma" in name:
        return "alma"
    raise ValueError(f"Unsupported distro for image: {image}")


# Per-distro shell snippet to install python3 + pip + venv and TLS roots.
_INSTALL_PYTHON = {
    "ubuntu": (
        "export DEBIAN_FRONTEND=noninteractive ; "
        "apt-get update -qq && "
        "apt-get install -y -qq python3 python3-pip python3-venv ca-certificates curl >/dev/null"
    ),
    "alma": (
        "dnf -y -q install python3 python3-pip ca-certificates >/dev/null"
    ),
}


# Per-distro shell snippet to install runtime libraries Chromium needs to launch.
# ``playwright install --with-deps`` only knows how to install via apt, so for
# Alma we install the equivalent set manually.
#
# Both the headed ``chromium`` and the ``chromium-headless-shell`` channels are
# installed explicitly: Playwright 1.50+ split them and ``launch(headless=True)``
# uses the headless-shell binary, which ``install chromium`` does not reliably
# fetch on its own.
#
# ``libXScrnSaver`` is intentionally absent from the Alma list — Alma 10 / RHEL 10
# dropped that package and dnf would otherwise print a non-fatal warning. Modern
# Chromium does not require it.
_INSTALL_BROWSER_DEPS = {
    "ubuntu": (
        "/opt/venv/bin/playwright install --with-deps chromium chromium-headless-shell >/dev/null"
    ),
    "alma": (
        "dnf -y -q install nss alsa-lib atk at-spi2-atk cups-libs libdrm libxkbcommon "
        "libXcomposite libXdamage libXfixes libXrandr libXtst pango cairo "
        "mesa-libgbm gtk3 >/dev/null ; "
        "/opt/venv/bin/playwright install chromium chromium-headless-shell >/dev/null"
    ),
}


# Click prompts in generate_pki.py read line-by-line from stdin; supply explicit
# values for every prompt so the test does not rely on default behaviour.
_PKI_PROMPT_ANSWERS = "\n".join([
    "GB",                          # Root: Country
    "England",                     # Root: State
    "London",                      # Root: Locality
    "OIDC VPN Test Org",           # Root: Organization
    "test-root.example.invalid",   # Root: Common Name
    "rootpass",                    # Root: passphrase
    "rootpass",                    # Root: passphrase confirm
    "GB",                          # Intermediate: Country
    "England",                     # Intermediate: State
    "London",                      # Intermediate: Locality
    "OIDC VPN Test Org",           # Intermediate: Organization
    "test-int.example.invalid",    # Intermediate: Common Name
    "intpass",                     # Intermediate: passphrase
    "intpass",                     # Intermediate: passphrase confirm
]) + "\n"


def _ovpn_directives_present(text: str) -> bool:
    """Confirm an OpenVPN client/server config contains expected configuration directives."""
    tokens = ("client", "dev tun", "remote ", "<ca>", "tls-crypt", "cipher ")
    return any(tok in text for tok in tokens)


def _extract_pem_block(text: str, tag: str) -> bytes:
    """Return the bytes inside <tag>...</tag> from an OpenVPN config."""
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    assert match, f"OVPN config missing <{tag}>...</{tag}> block"
    return match.group(1).strip().encode()


# ---------------------------------------------------------------------------
# Test 1 — generate a brand new PKI inside an Ubuntu LTS container
# ---------------------------------------------------------------------------

def test_pki_generation_in_ubuntu_lts(tmp_path, tools_dir):
    """Run pki_tool in a fresh Ubuntu LTS container and validate the materials it emits."""
    pki_tool_dir = tools_dir / "pki_tool"

    answers_file = tmp_path / "answers.txt"
    answers_file.write_text(_PKI_PROMPT_ANSWERS)

    out_dir = tmp_path / "pki"
    out_dir.mkdir()

    install = _INSTALL_PYTHON["ubuntu"]
    script = (
        f"{_CHOWN_TRAP}set -e ; {install} ; "
        "cd /tools ; "
        "python3 -m venv /opt/venv ; "
        "/opt/venv/bin/pip install --quiet -r requirements.txt ; "
        "/opt/venv/bin/python generate_pki.py generate-root "
        "--out-dir /work/pki --skip-entropy-validation < /work/answers.txt"
    )
    mounts = [
        (str(pki_tool_dir), "/tools", "ro"),
        (str(tmp_path), "/work", "rw"),
    ]
    result = _docker_run(UBUNTU_IMAGE, mounts, script)
    assert result.returncode == 0, (
        f"PKI generation failed in {UBUNTU_IMAGE}:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    expected = ["root-ca.key", "root-ca.crt", "intermediate-ca.key", "intermediate-ca.crt"]
    for name in expected:
        assert (out_dir / name).is_file(), f"Missing output file: {name}"

    root_cert = x509.load_pem_x509_certificate((out_dir / "root-ca.crt").read_bytes())
    int_cert = x509.load_pem_x509_certificate((out_dir / "intermediate-ca.crt").read_bytes())
    root_cn_values = [a.value for a in root_cert.subject]
    int_cn_values = [a.value for a in int_cert.subject]
    assert "test-root.example.invalid" in root_cn_values
    assert "test-int.example.invalid" in int_cn_values

    # Encrypted private keys must decrypt with the supplied passphrases
    serialization.load_pem_private_key(
        (out_dir / "root-ca.key").read_bytes(), password=b"rootpass"
    )
    serialization.load_pem_private_key(
        (out_dir / "intermediate-ca.key").read_bytes(), password=b"intpass"
    )


# ---------------------------------------------------------------------------
# Test 2 — fetch a server bundle from the live frontend in each distro
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("image", [UBUNTU_IMAGE, ALMA_IMAGE])
def test_server_bundle_in_distro_container(tmp_path, tools_dir, image):
    """Retrieve a server bundle in a fresh distro container and validate the extracted files."""
    psk = _create_psk(
        "server", f"distro-server-{_distro_kind(image)}-{int(time.time())}"
    )

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    install = _INSTALL_PYTHON[_distro_kind(image)]
    script = (
        f"{_CHOWN_TRAP}set -e ; {install} ; "
        "python3 -m venv /opt/venv ; "
        "/opt/venv/bin/pip install --quiet -r /tools/requirements.txt ; "
        "/opt/venv/bin/python /tools/get_openvpn_server_config.py "
        f"--server-url http://frontend:8600 --psk {shlex.quote(psk)} "
        "--target-dir /work/out --force"
    )
    mounts = [
        (str(tools_dir / "get_openvpn_config"), "/tools", "ro"),
        (str(tmp_path), "/work", "rw"),
    ]
    result = _docker_run(image, mounts, script)
    assert result.returncode == 0, (
        f"Server bundle fetch failed in {image}:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    extracted = sorted(p for p in out_dir.iterdir() if p.is_file())
    assert extracted, f"No files extracted to {out_dir}"

    # At least one PEM-format certificate is present and parseable
    pem_files = [p for p in extracted if p.read_bytes().startswith(b"-----BEGIN ")]
    assert pem_files, f"No PEM-format files extracted: {[p.name for p in extracted]}"
    cert_parsed = False
    for p in pem_files:
        if b"BEGIN CERTIFICATE" in p.read_bytes():
            x509.load_pem_x509_certificate(p.read_bytes())
            cert_parsed = True
            break
    assert cert_parsed, "Server bundle contained no parseable PEM certificate"

    # OpenVPN configuration injection: at least one config-style file must
    # contain a recognised directive.
    config_blobs = [
        p.read_text(errors="ignore") for p in extracted
        if p.suffix in (".conf", ".ovpn") or "openvpn" in p.name.lower()
    ]
    assert config_blobs, (
        f"Server bundle has no config file. Extracted: {[p.name for p in extracted]}"
    )
    assert any(_ovpn_directives_present(blob) for blob in config_blobs), (
        "Server bundle config files contain no recognised OpenVPN directives"
    )


# ---------------------------------------------------------------------------
# Test 3 — fetch a computer profile from the live frontend in each distro
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("image", [UBUNTU_IMAGE, ALMA_IMAGE])
def test_computer_profile_in_distro_container(tmp_path, tools_dir, image):
    """Retrieve a computer profile in a fresh distro container and validate its OpenVPN content."""
    psk = _create_psk(
        "computer", f"distro-computer-{_distro_kind(image)}-{int(time.time())}"
    )

    install = _INSTALL_PYTHON[_distro_kind(image)]
    script = (
        f"{_CHOWN_TRAP}set -e ; {install} ; "
        "python3 -m venv /opt/venv ; "
        "/opt/venv/bin/pip install --quiet -r /tools/requirements.txt ; "
        "/opt/venv/bin/python /tools/get_openvpn_computer_config.py "
        f"--server-url http://frontend:8600 --psk {shlex.quote(psk)} "
        "-o /work/computer.ovpn -f"
    )
    mounts = [
        (str(tools_dir / "get_openvpn_config"), "/tools", "ro"),
        (str(tmp_path), "/work", "rw"),
    ]
    result = _docker_run(image, mounts, script)
    assert result.returncode == 0, (
        f"Computer profile fetch failed in {image}:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    profile = tmp_path / "computer.ovpn"
    assert profile.is_file(), "Computer profile file not produced"
    text = profile.read_text(errors="ignore")
    assert _ovpn_directives_present(text), (
        f"Computer profile missing recognised OpenVPN directives. Head:\n{text[:500]}"
    )
    ca_pem = _extract_pem_block(text, "ca")
    x509.load_pem_x509_certificate(ca_pem)


# ---------------------------------------------------------------------------
# Test 4 — fetch a user profile via the OIDC flow with Playwright in-container
# ---------------------------------------------------------------------------

# Driver script written into the container's /work mount and executed by the
# in-container Python venv. Spawns the CLI in the background, waits for the
# auth URL it writes, drives the OIDC login with Playwright, and waits for the
# CLI to finish writing the OVPN profile.
_USER_PROFILE_DRIVER = r'''
import os
import re
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

URL_FILE = "/work/url.txt"
PROFILE_OUT = "/work/user.ovpn"
USER_TYPE = os.environ.get("OIDC_USER_TYPE", "it")

cli = subprocess.Popen(
    [
        "/opt/venv/bin/python", "/tools/get_openvpn_profile.py",
        "--server-url", "http://frontend:8600",
        "-o", PROFILE_OUT,
        "-f",
        "--output-auth-url", URL_FILE,
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

deadline = time.time() + 60
auth_url = None
while time.time() < deadline:
    if os.path.exists(URL_FILE) and os.path.getsize(URL_FILE) > 0:
        candidate = open(URL_FILE).read().strip()
        if candidate:
            auth_url = candidate
            break
    time.sleep(0.5)

if not auth_url:
    cli.kill()
    out, err = cli.communicate(timeout=5)
    sys.stderr.write("CLI stdout:\n" + out.decode(errors="ignore") + "\n")
    sys.stderr.write("CLI stderr:\n" + err.decode(errors="ignore") + "\n")
    raise SystemExit("Timed out waiting for CLI to publish auth URL")

print(f"Driving OIDC flow at: {auth_url}")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(auth_url, wait_until="networkidle", timeout=30000)
    button = page.locator(f'button:has-text("Login as {USER_TYPE}")')
    button.wait_for(state="visible", timeout=15000)
    button.click()
    try:
        page.wait_for_url(re.compile(r"http://localhost:\d+.*token="), timeout=30000)
    except Exception:
        # Callback page closes itself after the token lands; missing the
        # navigation here is not fatal as long as the CLI completes.
        pass
    browser.close()

rc = cli.wait(timeout=90)
out, err = cli.communicate()
sys.stdout.write(out.decode(errors="ignore"))
sys.stderr.write(err.decode(errors="ignore"))
sys.exit(rc)
'''


@pytest.mark.parametrize("image", [UBUNTU_IMAGE, ALMA_IMAGE])
def test_user_profile_in_distro_container(tmp_path, tools_dir, image):
    """Retrieve a user profile in a fresh distro container, including driving the OIDC flow with Playwright."""
    driver_path = tmp_path / "driver.py"
    driver_path.write_text(_USER_PROFILE_DRIVER)

    distro = _distro_kind(image)
    install = _INSTALL_PYTHON[distro]
    install_browser = _INSTALL_BROWSER_DEPS[distro]
    script = (
        f"{_CHOWN_TRAP}set -e ; {install} ; "
        "python3 -m venv /opt/venv ; "
        "/opt/venv/bin/pip install --quiet -r /tools/requirements.txt playwright ; "
        f"{install_browser} ; "
        "/opt/venv/bin/python /work/driver.py"
    )
    mounts = [
        (str(tools_dir / "get_openvpn_config"), "/tools", "ro"),
        (str(tmp_path), "/work", "rw"),
    ]
    result = _docker_run(
        image, mounts, script, timeout=1500,
        env={"OIDC_USER_TYPE": OIDC_USER_TYPE},
    )
    assert result.returncode == 0, (
        f"User profile fetch failed in {image}:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    profile = tmp_path / "user.ovpn"
    assert profile.is_file(), "User profile file not produced"
    text = profile.read_text(errors="ignore")
    assert _ovpn_directives_present(text), (
        f"User profile missing recognised OpenVPN directives. Head:\n{text[:500]}"
    )
    ca_pem = _extract_pem_block(text, "ca")
    x509.load_pem_x509_certificate(ca_pem)
    # User profiles must carry an embedded client certificate
    cert_pem = _extract_pem_block(text, "cert")
    x509.load_pem_x509_certificate(cert_pem)
