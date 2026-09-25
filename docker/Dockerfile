# syntax=docker/dockerfile:1.6
#
# Production image: frappe + verp_staffing + vruglechat (vruglechat is baked in
# but NOT installed on any site by default; install it per site with add-app.sh).
#
# Build (see build.sh):  needs BuildKit + a git token secret for the private repos.

ARG FRAPPE_VERSION=v15.119.1

# ---------- builder ----------
FROM frappe/build:${FRAPPE_VERSION} AS builder

ARG FRAPPE_BRANCH=version-15
ARG FRAPPE_PATH=https://github.com/frappe/frappe
ARG GIT_HOST=git.vrugle.com

COPY --chown=frappe:frappe apps.json /opt/apps.json

USER frappe
WORKDIR /home/frappe

# The token only exists during this RUN (BuildKit secret) and is never written
# to an image layer; the global git config lives in the builder stage only.
RUN --mount=type=secret,id=git_token,uid=1000 \
    git config --global url."https://oauth2:$(cat /run/secrets/git_token)@${GIT_HOST}/".insteadOf "https://${GIT_HOST}/" \
 && bench init --skip-redis-config-generation \
      --frappe-branch=${FRAPPE_BRANCH} --frappe-path=${FRAPPE_PATH} \
      --apps_path=/opt/apps.json /home/frappe/frappe-bench \
 && cd /home/frappe/frappe-bench \
 && echo "{}" > sites/common_site_config.json \
 && find apps -mindepth 1 -path "*/.git" | xargs rm -rf \
 && cp -r sites/assets /home/frappe/assets-baked

# ---------- runtime ----------
FROM frappe/base:${FRAPPE_VERSION} AS runtime

USER frappe
COPY --from=builder --chown=frappe:frappe /home/frappe/frappe-bench /home/frappe/frappe-bench
# Pristine copy of built assets. The `sites` volume shadows sites/assets, so the
# configurator re-syncs it from here on every start (keeps upgrades correct).
COPY --from=builder --chown=frappe:frappe /home/frappe/assets-baked /home/frappe/assets-baked
COPY --chown=frappe:frappe scripts/configure.sh /usr/local/bin/configure.sh

WORKDIR /home/frappe/frappe-bench
VOLUME ["/home/frappe/frappe-bench/sites", "/home/frappe/frappe-bench/logs"]

CMD ["/home/frappe/frappe-bench/env/bin/gunicorn", \
     "--chdir=/home/frappe/frappe-bench/sites", "--bind=0.0.0.0:8000", \
     "--threads=4", "--workers=2", "--worker-class=gthread", \
     "--worker-tmp-dir=/dev/shm", "--timeout=120", "--preload", \
     "frappe.app:application"]
