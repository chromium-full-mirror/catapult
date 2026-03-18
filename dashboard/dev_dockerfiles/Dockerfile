FROM google/cloud-sdk:468.0.0

ENV PATH=/usr/local/depot_tools:${PATH}

# The latest version is in sid repo. So need to specify the
# version of dependency to avoid version conflix if you want
# to use "stable" one.
RUN apt-get --allow-releaseinfo-change update && apt-get install -y \
  libprotoc23 \
  protobuf-compiler \
  git \
  && git clone https://chromium.googlesource.com/chromium/tools/depot_tools /usr/local/depot_tools \
  && /usr/local/depot_tools/vpython3 -c ''

ENV PYTHONPATH=/usr/lib/google-cloud-sdk/platform/google_appengine

COPY docker-entrypoint.sh /usr/local/bin/

ENTRYPOINT ["docker-entrypoint.sh"]
