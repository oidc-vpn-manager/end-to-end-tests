#! /bin/bash
generate_next_semver() {
    RE='[^0-9]*\([0-9]*\)[.]\([0-9]*\)[.]\([0-9]*\)\([0-9A-Za-z-]*\)'

    step="${2:-patch}"

    base="${1:-}"
    if [ -z "$base" ]
    then
        base="$(git tag -l --no-column 2>/dev/null | tail -n 1)"
        if [ -z "$base" ]
        then
            echo "v1.0.0"
            return 0
        fi
    fi

    MAJOR="$(echo "$base" | sed -e "s#$RE#\1#")"
    MINOR="$(echo "$base" | sed -e "s#$RE#\2#")"
    PATCH="$(echo "$base" | sed -e "s#$RE#\3#")"

    case "$step" in
    major)
        ((MAJOR+=1))
        ((MINOR=0))
        ((PATCH=0))
        ;;
    minor)
        ((MINOR+=1))
        ((PATCH=0))
        ;;
    patch)
        ((PATCH+=1))
        ;;
    esac

    echo "v${MAJOR}.${MINOR}.${PATCH}"
}

semver_bump() {
    pushd "${1:-/some/path/which/doesnt/exist}" || return 1

    # Abort if there are uncommitted changes — the tag must point to a clean commit
    if ! git diff --quiet || ! git diff --staged --quiet; then
        echo "❌ ERROR: Uncommitted changes in $(pwd). Commit everything before releasing."
        popd || return 1
        return 1
    fi

    # Get the latest commit hash
    latest_commit=$(git rev-parse HEAD)
    echo "🔸 Latest commit: $latest_commit"

    # Check if this commit is already tagged
    if git tag --points-at HEAD | grep -q .; then
        echo "✅ Latest commit is already tagged:"
        git tag --points-at HEAD
    else
        echo "⚠️  Latest commit is not tagged"
        
        # Get the current highest tag or default to 1.0.0
        current_tag=$(git tag -l --no-column 2>/dev/null | sort -V | tail -n 1)
        if [ -z "$current_tag" ]; then
            current_tag=""
            echo "🔸 No existing tags found, starting from v1.0.0"
        else
            echo "🔸 Current highest tag: $current_tag"
        fi
        
        # Use semver_bump to get the next version
        new_tag=$(generate_next_semver "$current_tag" "${BUMP:-patch}")
        echo "🏷️  Creating new tag: $new_tag"
        
        # Create and push the tag
        git tag -a "$new_tag" -m "Auto-tagged as part of release process"
        echo "✅ Created tag: $new_tag"
        
        # Optionally push the tag (uncomment the next line if you want to push immediately)
        # git push origin "$new_tag"
        # echo "📤 Pushed tag: $new_tag"
    fi
    popd || return 1
}