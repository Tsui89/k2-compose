FROM python:2.7-alpine
ARG branch
ARG commit
ARG buildtime
ARG owner
LABEL branch=$branch \
        commit=$commit \
        buildtime=$buildtime \
        owner=$owner

RUN pip install docker-compose==1.14.0 pytz colorclass terminaltables pick -i http://pypi.douban.com/simple --trusted-host pypi.douban.com

COPY README.rst /docs/
# put your commands here
COPY k2_compose /opt/k2-compose/
COPY setup.py version /opt/k2-compose/
WORKDIR /opt/k2-compose
RUN python setup.py install

ENTRYPOINT ["ping", "localhost"]
