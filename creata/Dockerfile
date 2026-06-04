#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with Apache Airflow for additional information
# regarding copyright ownership. The ASF licenses this file to you under
# the Apache License, Version 2.0.
#
FROM apache/airflow:3.2.2

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

USER root

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg unixodbc-dev libgssapi-krb5-2; \
    debian_version="$(grep VERSION_ID /etc/os-release | cut -d '"' -f 2 | cut -d '.' -f 1)"; \
    if [[ ! " 9 10 11 12 13 " =~ " ${debian_version} " ]]; then \
      echo "Debian ${debian_version} is not supported by Microsoft ODBC Driver 18"; \
      exit 1; \
    fi; \
    curl -sSL -O "https://packages.microsoft.com/config/debian/${debian_version}/packages-microsoft-prod.deb"; \
    dpkg -i packages-microsoft-prod.deb; \
    rm packages-microsoft-prod.deb; \
    apt-get update; \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

USER airflow

COPY requirements.txt /tmp/creata-airflow-requirements.txt
RUN pip install --no-cache-dir -r /tmp/creata-airflow-requirements.txt
