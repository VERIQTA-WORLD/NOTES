FROM postgres:17-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends gnupg awscli && rm -rf /var/lib/apt/lists/*
COPY recovery/kube-backup.sh /backup.sh
ENTRYPOINT ["bash", "/backup.sh"]
