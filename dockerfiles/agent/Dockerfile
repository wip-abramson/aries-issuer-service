FROM bcgovimages/von-image:py36-1.15-0
#FROM bcgovimages/aries-cloudagent:py36-1.15-1_0.6.0


USER root
RUN apt-get update
RUN apt-get update && apt-get install -y gcc


RUN pip3 install aries-cloudagent

ADD https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64 ./jq
RUN chmod +x ./jq
COPY scripts/startup.sh startup.sh
RUN chmod +x ./startup.sh
COPY scripts/ngrok-wait.sh wait.sh
RUN chmod +x ./wait.sh

USER $user

CMD ./wait.sh ./startup.sh