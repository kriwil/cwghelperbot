FROM python:3.6.5
ENV PYTHONUNBUFFERED 1
ENV PIPENV_VENV_IN_PROJECT 0

RUN pip install pipenv
RUN mkdir /app
WORKDIR /app
COPY Pipfile /app/Pipfile
COPY Pipfile.lock /app/Pipfile.lock
RUN pipenv install --ignore-pipfile
COPY . /app

CMD ["pipenv", "run", "python", "bot.py"]
