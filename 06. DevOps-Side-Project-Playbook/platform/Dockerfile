FROM registry.k8s.io/kubectl:v1.32.2 AS kubectl
FROM python:3.12-slim-bookworm
COPY --from=kubectl /bin/kubectl /usr/local/bin/kubectl
COPY tools/environments.py /environments.py
ENV HOME=/tmp
USER 10001:10001
ENTRYPOINT ["python", "/environments.py"]
