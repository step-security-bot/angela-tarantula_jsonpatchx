FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:08ec1e1c3c7d558f987cd78488d10ce32a797cf6b670e4f35a3ea63c22809866

# Pin dependencies
COPY .clusterfuzzlite/requirements-bootstrap.txt /tmp/requirements-bootstrap.txt

# Default Python 3.11 is no good for jsonpatchx which is Py3.12+
RUN python3 -m pip install --disable-pip-version-check --require-hashes \
      --only-binary=:all: -r /tmp/requirements-bootstrap.txt && \
    uv python install 3.13 && \
    PYTHON_BIN="$(uv python find 3.13)" && \
    "$PYTHON_BIN" -m venv /opt/python313

ENV PATH="/opt/python313/bin:${PATH}"

COPY . $SRC/jsonpatchx
WORKDIR $SRC/jsonpatchx

# Install dependencies with Py3.13
RUN . /opt/python313/bin/activate && \
    uv sync --python /opt/python313/bin/python --no-dev --group fuzz --active

COPY .clusterfuzzlite/build.sh $SRC/
