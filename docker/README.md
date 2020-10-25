```
git clone https://github.com/karlicoss/promnesia.git
cd promnesia/docker
docker-compose build; and docker-compose up
```
you should eventually see:
```
indexer_1  | FileNotFoundError: [Errno 2] No such file or directory: '/data/indexer-config.py'
```

in another terminal:

```
cp indexer-config.py.example ../data/indexer-config.py
cd data/
echo "i like https://github.com/karlicoss/promnesia" >> my_notes.txt
git clone https://github.com/karlicoss/exobrain
git clone https://github.com/koo5/notes.git
...
```
the config file will be periodically reloaded by the indexer process, and data will be periodically re-indexed.

