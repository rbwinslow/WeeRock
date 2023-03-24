# WeeRock – My take-home exercise for WeeCare

Hello, nice WeeCare people!

I know there is a stated preference for PHP in the instructions for this homework, but I availed myself of your openness to other languages because I anticipated that there would be many instances where intuitions about the Web framework and its ecosystem would be important, and my strongest framework depth right now is in Django.

## Overview

Speaking of consequential decisions based on the framework and its ecosystem, one of the first and biggest decisions I made in the design of this project was to forego usage of the Django REST Framework, which is what basically everybody uses if they're building a REST API such as the one called for in this exercise.

[DRF](https://www.django-rest-framework.org/) provides both high-level and low-level abstractions. The former are very opinionated, integrated and declarative, while the latter are more general and customizable, and thus more verbose. Despite the natural inclination to use the industry standard tool, its introduction would have forced one of two problematic courses:

- Produce a strongly DRF-flavored solution, where the framework makes almost all the design decisions and my own material contributions are minimal. In this scenario, I'm demonstrating more about my familiarity with Django and DRF than the sort of versatility and nuts-and-bolts competence that I think this exercise is meant to showcase.
- Lean on DRF's customized lower-level abstractions to demonstrate my own interface design thoughts distinct from DRF's. This is still a situation in which the two frameworks end up doing lots of the work, and the shape and emphasis of the stuff I build is still more DRF-shaped than broadly Web-API-shaped, again somewhat at odds with the exercise.

So I built this service as a Django application, hoping that the framework's boundaries and the shape of my own contributions would do well enough illustrating an approach to building an API service gracefully on top of a Web framework.

### Noteworthy Omissions

Limitations or other compromises pertaining to the "awesomeness" features are noted in the discussion of my design of those features, in the subsections below. Here are some other, floating maturity features that this project, so far, lacks:

- **TBD infra:** I started thinking about DevOps for this, and created and `infra` directory, but left it behind as I pursued the main "awesomeness" goals.
- **No TLS:** Especially egregious considering I chose Basic Auth for the authentication scheme, but all the red tape wasn't the best bang for the buck, demonstration-wise, I felt.
- **No Permissions:** I hacked up a little authentication, as explained further below, but I didn't get as far as dreaming up permissions.
- **No Key Management:** The `SECRET_KEY` value is just the hard-coded one from scaffolding, regardless of environment.

Seeing a theme? Good security takes time.

### Where Things Are

The project structure here is scaffolded by Django, and I committed the original workspace, so git history should show all I've done.

The top-level `WeeRock` directory contains application globals like configuration and routing, where I've done modest edits (particularly setting up separate configurations for dev and prod), but almost all the action in which you're interested is under the `top_albums` package.

### Running the Project

I did this work in PyCharm, where the Django plugin (factory equipment) makes it easy to run manage.py commands (this is Django's per-project CLI) while the virtualenv integration handles python virtualization. I think that just setting up a virtualenv for this project (python 3.8 or higher) and then running `pip install -r requirements.txt` should get you up-and-running for dev, at least, but if you run into trouble, let me know and we can work through it.

You can tell you're good if this works (when it's working, it prints out documentation for the RESTful API):

`python3 manage.py apidocs`

If that _does_ work, then you do this to get the service started and accessible locally:

`python3 manage.py runserver`

Django will give you a URL to hit, and just `GET`ting that (the root) should give you health check output (which also includes the API docs as a JSON string with newline escapes in it, because why not?). 

## "Novice" Requirements

### A clean & modern API for retrieving the top albums from the iTunes feed

You'll find the GET view, along with the other CRUD operations, implemented and documented in `album_view.py`.

As discussed below, these data are queried from the application's database. See below to understand how the iTunes feed data end up there.

The response structure is based closely on the schema I ended up deriving from feed data.

### API documentation

A mature project would likely be using Swagger, as integrated with Django REST Framework, to generate an awesome site with built-in experimentation and all that jazz. Since I elected to avoid DRF (as discussed in the _Overview_), I've instead hacked together a couple of mechanisms for gathering up and displaying the long docstrings I've written for each of the top-albums API methods:

- `python3 manage.py apidocs` (This is implemented in `top_albums/management/commands/apidocs.py`)
- In health check output: `curl --silent http://<domain>/ | jq -r .apidocs`

Each endpoint method's documentation includes a `curl` command illustration that should work with the local server when running the dev server through `manage.py runserver`.

### Tests

I've written integration tests for various top-albums API features, as well as iTunes feed downloading and merging (see below) and the health check. They're all under `top_albums/tests`.

The tests aren't very exhaustive, but they do demonstrate my testing style proclivities, for better or worse.

## "Intermediate" Requirements

### Store data in a SQL database

I'm doing this, though one glaring omission in this area is the fact that I haven't set up a proper production database; it's all SQLite3. I was planning to address this when I went the extra mile on DevOps (local Kubernetes and GKE, Helm), which I haven't done yet.

Django mandates data migrations (its own), and all management of DDL is through their ORM and its `Model` abstraction. Hence, I've written no SQL to set up the schema, because that's not something a Django dev would ever do. You'll find the models in `models.py` and the automatically generated data migrations under `top_albums/migrations`.

I made iTunes categories a one-to-many relationship with albums for obvious reasons, but I denormalized images even though they're represented as a simple list in the RSS feed. I discuss my decision-making around this in `models.py`.

To populate the database from the current list provided by Apple, I wrote a "download" manage.py sub-command that downloads the feed and merges its contents into the database:

    python3 manage.py download
   
By "merging," I mean top albums from the feed are upserted, and any existing albums in the table that weren't in the feed have their "top" status taken away (`is_itunes_top = False`) but they aren't deleted.

### Additional filtering options to restrict and/or sort on data

The GET endpoint offers pretty powerful sorting (multi-level on several fields, with descending option on any level) and filtering (channelling the Django ORM's own "__op" suffix convention to offer all sorts of comparison operations). These are documented in the API documentation, including a handful of examples.

## "Expert" Requirements

### CRUD endpoints

`/top-albums/` accepts POST, PATCH and DELETE requests, all of which are documented in detail on their respective view methods. These endpoints require authentication (next subhead), and the PATCH and DELETE both require an id slug in the URL following `/top-albums/` to identify the album being updated or deleted, respectively.

When POSTing a new album, you have to specify an `id` value, because this service delegates `id` origination to other actors (mainly Apple). Handle this as you see fit.

There is no CRUD for iTunes categories, partially on the assumption that downloading top albums will populate enough of them to be useful (and there doesn't appear to be any direct feed for these entities from Apple).

### User authentication

This is an area where the approach would be very different if I had chosen to base the API on Djang REST Framework. Instead, I hacked up a very minimal Basic Auth solution based on the factory-equipped user management and authentication features in Django.

To set up a user who can authenticate, you want to use the Django [Python shell](https://docs.djangoproject.com/en/4.1/ref/django-admin/#shell): `python3 manage.py shell`

Once you're there, do something like this:

    from django.contrib.auth.models import User
    User.objects.create_user("richard", "richard@email.com", "Password#1")

Use the `curl --user` argument, as illustrated in the API documentation, to do Basic Auth with the username and password you set up here.

## Bonus Features

### Pagination

The GET endpoint provides an optional pagination strategy, with HATEOAS-flavored `previous_page` and `next_page` URLs in the response. If you specify nothing in the request, you get a single "page" with `page_size` equal to the number of results.

### Health check

Already mentioned above, but I'll note that in addition to providing API docs this (root) endpoint does actually attempt a database connection, and reports on that success or failure (the logic for which is plagiarized, as noted in comments).
