# Contributing to SnowIn

Install Python 3.12 or newer, then set up the package and development tools:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[nisar,geometry,dask]" --group dev
pytest -q
ruff check .
ruff format --check .
```

Add tests and docstring updates with public behavior. Keep notebooks as examples,
not as the home of core logic. Scientific changes should follow the
[testing policy](maintainer/testing.md) and preserve the documented
[scientific conventions](docs/scientific_conventions.md).

A pull request should address one focused change, describe the behavior, and
report relevant validation. Do not commit generated caches, plots, local data,
or credentials.
