FROM python

RUN mkdir /data \
    mkdir /usr/src/promnisia

WORKDIR /usr/src/promnesia
COPY src/ .
COPY setup.py /usr/src/

#RUN python /usr/src/setup.py #LookupError: setuptools-scm was unable to detect version for '/usr/src/promnesia'.

RUN pip install --no-cache-dir more_itertools pytz sqlalchemy cachew \
                appdirs urlextract python-magic \
                tzlocal hug \
                logzero HPI beautifulsoup4 lxml mistletoe orgparse dataset

ENV PPATH=/usr/src/promnesia:${PPATH}
VOLUME /data

EXPOSE 13131
CMD ["python", "-m", "promnesia", "serve", "--db", "/data/promnesia.sqlite", "--port", "13131"]
