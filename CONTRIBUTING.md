# Contributing

Start with a reproducible issue using synthetic inputs. Explain the expected behavior, actual behavior, tool version and whether the failure concerns JSON checks, XML, UI, provider or simulator integration.

Install the dev extra, run pytest and Ruff, then frontend typecheck/build if the UI changed. Keep new features within the documented subset or update the scope and tests together. Test unsupported input and failure paths; do not convert NOT_RUN/UNSUPPORTED into PASS to make a report look successful.

Submit a focused pull request with the relevant tests and any compatibility limitations. No credentials, real account data, simulator binaries, private scenarios or third-party assets without redistribution rights. AI-assisted contributions are welcome; contributors remain responsible for reviewing the code and its provenance.

By submitting changes you confirm you have the right to contribute them under the repository's MIT license. Public dependencies retain their own license requirements.
