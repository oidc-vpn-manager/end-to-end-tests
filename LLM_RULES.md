# THE RULES

1. Any time you try to access a new directory, you MUST use the full path to that directory to conserve tokens.
2. To preserve privacy, you must not credit any LLM in any git commits.
3. Documentation MUST be kept up to date, whether that's files in docs/, the submodule README.md files, Swagger files, LLM_INTRO.md or LLM_RULES.md files, or any analysis documentation created (function mappings, docstring audits, etc.).

## Testing

1. Full E2E testing takes a LONG time. Ask the user to run the full E2E test suite. Other testing (including individual files in the E2E tests) can be performed without issues as part of your normal operations.
2. "100% Green" is shorthand for "All tests results must contain no errors, no warnings, no criticals, no failures and no skipped tests. Code coverage must be at 100%". That something is an edge case isn't sufficient for it to be written off as a line which can be skipped or ignored. If you can't get code coverage or it will be incredbily tricky to achieve coverage of that line, ask what to do.
3. You must NEVER implement a no-coverage exception to avoid code coverage, but if you feel one is necessary, please provide the code line and justification, and I'll consider implementing it.
4. You must NEVER implement a test which would be skipped; tests must pass or fail in preparation to be fixed.
5. Whenever new code is written or code is modified to progress a task, tests must be written to confirm the code performs as expected.
6. Tests must confirm that the happy path works ("this test does what I expect it to do") but also some consideration for not-happy paths. When searching for inspiration around how to test the not-happy paths, consider the lens of the OWASP Top 10 (e.g. "if I try to send a SQL injection attack to this endpoint, because of the protections in place, it will not work"), the OWASP API Top 10 (e.g. "If I try to access this without authenticating, because of the protections in place, that access will be rejected") and the OWASP Infrastructure Top 10 - excluding external controls such as WAF and monitoring tools (e.g. "Because of the at-rest encryption, this file is not accessible in plain-text on disk"), as well as considering the viewpoint of a Red-Team attacker, a Blue-Team defender and a bug bounty hunter.
7. Recognise that some not-happy paths will already have protections at the flask layer, or with the flask add-ons we've implemented, and thus don't require testing or are even unable to be tested. If we decide not to write tests, create a .md file in the relevant test directory with tests that would have been implemented and the reasons they were skipped.

## Documentation Standards

1. **Function Documentation**: All functions must have comprehensive docstrings including purpose, parameters, return values, exceptions, and examples.
2. **Architecture Documentation**: When creating function call mappings or route-to-function chains, ensure they're comprehensive and traceable for debugging purposes.
3. **Security Documentation**: Always document security implications, timing attack prevention, input validation, and cryptographic considerations.
