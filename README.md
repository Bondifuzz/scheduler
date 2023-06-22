# Scheduler

## Deployment

Download repository

```bash
git clone https://github.com/Bondifuzz/scheduler.git
cd scheduler
```

Build docker image

```bash
docker build -t scheduler .
```

Run container (locally)

```bash
docker run --net=host --rm -it --name=scheduler --env-file=.env scheduler bash
```

## Local development

### Clone scheduler repository

All code and scripts are placed to scheduler repository. Let's clone it.

```bash
git clone https://github.com/Bondifuzz/scheduler.git
cd scheduler
```

### Start services scheduler depends on

Then you should invoke `docker-compose` to start all services scheduler depends on.

```bash
ln -s local/dotenv .env
ln -s local/docker-compose.yml docker-compose.yml
docker-compose -p scheduler up -d
```

### Run scheduler

Finally, you can run scheduler service:

```bash
# Install dependencies
pip3 install -r requirements-dev.txt

# Run service
python3 -m scheduler
```

### VSCode extensions

```bash
# Python
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance

# Spell cehcking
code --install-extension streetsidesoftware.code-spell-checker

# Config
code --install-extension redhat.vscode-yaml
code --install-extension tamasfe.even-better-toml

# Markdown
code --install-extension bierner.markdown-preview-github-styles
code --install-extension yzhang.markdown-all-in-one

# Developer
code --install-extension Gruntfuggly.todo-tree
code --install-extension donjayamanne.githistory
```

### Code documentation

TODO

### Running tests

```bash
# Install dependencies
pip3 install -r requirements-test.txt

# Run unit tests
pytest -vv scheduler/tests/unit

# Run functional tests
pytest -vv scheduler/tests/integration
```

### Spell checking

Download cspell and run to check spell in all sources

```bash
sudo apt install nodejs npm
sudo npm install -g cspell
cspell "**/*.{py,md,txt}"
```