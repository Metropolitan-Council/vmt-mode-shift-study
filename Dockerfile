FROM condaforge/mambaforge AS build

    COPY linux_environment.yml environment.yml
    RUN mamba env create -f environment.yml

    RUN mamba install conda-pack

    RUN conda-pack -n gis -o /tmp/env.tar && \
        mkdir /venv && cd /venv && tar xf /tmp/env.tar && \
        rm /tmp/env.tar

    RUN /venv/bin/conda-unpack

FROM python:3.9-slim AS runtime

    COPY --from=build /venv /venv

    WORKDIR /app
    EXPOSE 8051

    COPY /src/analysis_tool /app
    COPY docker_run.bash /app

    SHELL ["/bin/bash", "-c"]

    RUN chmod +x /app/docker_run.bash
    ENTRYPOINT ["/app/docker_run.bash"]
