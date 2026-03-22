# jsonpatchx

<!-- markdownlint-disable MD013 -->

[![Release](https://img.shields.io/github/v/release/angela-tarantula/jsonpatchx?display_name=tag)](CHANGELOG.md)
[![Tests](https://img.shields.io/github/actions/workflow/status/angela-tarantula/jsonpatchx/python-app.yml?branch=main&label=CI&style=flat)](https://github.com/angela-tarantula/jsonpatchx/actions)
![RFC 6902 compatible core](https://img.shields.io/badge/RFC-6902-blue)
![FastAPI ready](https://img.shields.io/badge/FastAPI-First%20Class-009688)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/angela-tarantula/jsonpatchx/badge)](https://scorecard.dev/viewer/?uri=github.com/angela-tarantula/jsonpatchx)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-3.0-fbab2c.svg)](CODE_OF_CONDUCT.md)

<!-- markdownlint-enable MD013 -->

## About The Project

[RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902) (JSON Patch) is
intentionally minimal and transport-focused. That minimalism is great for
interoperability, but in modern distributed systems, PATCH crosses trust
boundaries: browser clients, internal services, third-party integrations, and
increasingly LLM-generated patch payloads.

### jsonpatchx provides the RFC core and adds an API contract layer

- **Input Safety**: patch operations are Pydantic models, so invalid payloads
  fail early with clear errors.
- **Surface Control**: operations can be allow-listed per route to limit what
  clients can do.

### It also provides extensibilty beyond the RFC

- **API Meaning**: define custom patch operations (toggle, increment, etc.) so
  updates target intent, not brittle positional assumptions.
- **Typed Targeting**: operations are explicit, so pointers can participate in
  typed contracts with clear failure modes when a resolved path violates
  expected structure or type.
- **Advanced Path Selection**: choose your path strategy
  ([JSON Pointer](https://datatracker.ietf.org/doc/html/rfc9535),
  [JSONPath](https://datatracker.ietf.org/doc/html/rfc6901), or your custom
  resolver) so you can enable non-positional selection such as filtering,
  matching, or multi-target updates.

### And it treats the patch layer as a first-class contract

- **Contract Drift**: OpenAPI is generated from the same runtime patch models,
  so documentation stays aligned automatically.
- **Versioning**: evolve operation contracts over time with schema changes
  rather than protocol rewrites.
- **FastAPI Integration**: set up PATCH routes quickly with minimal boilerplate.

### This is a Safe Space

jsonpatchx is intentionally designed as a safe experimentation surface: teams
can introduce richer operations, compare patterns in production, and let the
best designs emerge. With JSONPath now standardized in
[RFC 9535](https://datatracker.ietf.org/doc/html/rfc9535), custom pointer
backends make it practical to explore more expressive targeting while preserving
an RFC 6902-compatible core.

## Getting Started

Install from PyPI:

### Installation

```sh
pip install jsonpatchx
```

## Usage

Basic patch application:

```python
from jsonpatchx import JsonPatch

doc = {"name": "Ada", "roles": ["engineer"]}

patch = JsonPatch.from_string(
    """
    [
      {"op": "replace", "path": "/name", "value": "Ada Lovelace"},
      {"op": "add", "path": "/roles/-", "value": "maintainer"}
    ]
    """
)

updated = patch.apply(doc)
```

For practical end-to-end examples:

- FastAPI demos: [examples/fastapi/README.md](examples/fastapi/README.md)
- Operation recipes: [examples/recipes.py](examples/recipes.py)
- Error payload shapes: [docs/demo-error-shapes.md](docs/demo-error-shapes.md)

## Roadmap

See the [open issues](https://github.com/angela-tarantula/jsonpatchx/issues) for
a list of proposed features (and known issues).

## Contributing

Contributions are what make the open source community such an amazing place to
learn, inspire, and create. Any contributions you make are **greatly
appreciated**. For detailed contributing guidelines, please see
[CONTRIBUTING.md](CONTRIBUTING.md)

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## Contact

Anglea Liss - [chamsester@gmail.com](mailto:chamsester@gmail.com)

Project Link:
[https://github.com/angela-tarantula/jsonpatchx](https://github.com/angela-tarantula/jsonpatchx)

## Acknowledgements

Thanks to these foundational projects:

- [Pydantic](https://docs.pydantic.dev/latest/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [python-json-pointer](https://github.com/stefankoegl/python-json-pointer)
- [python-jsonpath](https://github.com/jg-rp/python-jsonpath)

And to these excellent alternatives:

- [py_yyjson](https://tkte.ch/py_yyjson/#patch-a-document)
- [json-merge-patch](https://github.com/OpenDataServices/json-merge-patch)
- [python-json-patch](https://github.com/stefankoegl/python-json-patch)
