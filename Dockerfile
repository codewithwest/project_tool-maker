FROM python:3.12-slim

RUN pip install uv --no-cache-dir

RUN uv tool install llm-tool-maker[postgres] --system

EXPOSE 5000

CMD ["llm-tool-maker", "ui"]
