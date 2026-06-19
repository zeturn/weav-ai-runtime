# Contributing

Thanks for improving this package.

## Development Setup

```bash
python -m pip install -e ".[dev]" --no-deps
```

Use `--no-deps` when validating the package shell without installing migration-time upstream packages. Use a normal editable install when you need full integration coverage.

## Checks

Run these before opening or merging a pull request:

```bash
python -m pytest
python -m build --wheel
```

## Pull Request Checklist

- Tests cover changed public behavior.
- README or inline docs are updated when the public API changes.
- Dependency changes are intentional and versioned.
- Security-sensitive behavior is called out in the PR description.
- Release impact is clear, especially for downstream packages.

## License

Unless stated otherwise, contributions are submitted under the Apache-2.0 license used by this repository.
