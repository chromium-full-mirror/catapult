# Set up an image that just runs the datastore emulator.
FROM google/cloud-sdk:latest

RUN apt-get update && apt-get install -y wget
RUN wget -q https://download.oracle.com/java/21/latest/jdk-21_linux-x64_bin.tar.gz && \
    tar xzf jdk-21_linux-x64_bin.tar.gz && \
    rm jdk-21_linux-x64_bin.tar.gz

# The extracted directory name might vary, but usually it's jdk-21.x.x
# Let's find it and set PATH
RUN ln -s /jdk-21* /jdk21
ENV PATH="/jdk21/bin:${PATH}"

ARG emulator_port=8888
ARG emulator_project=chromeperf
ARG emulator_host=0.0.0.0
ENV EMULATOR_HOST $emulator_host
ENV EMULATOR_PORT $emulator_port
ENV EMULATOR_PROJECT $emulator_project

# TODO(dberris): Figure out how to signal this container to shutdown externally.
CMD gcloud beta emulators datastore start \
        --project "$EMULATOR_PROJECT" \
        --host-port="$EMULATOR_HOST:$EMULATOR_PORT" \
        --no-store-on-disk \
        --consistency=1.0