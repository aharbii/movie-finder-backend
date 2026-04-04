-- Create a dedicated test database on the first postgres bootstrap so the
-- Docker-only `make test` flow does not mutate the developer's local data.
CREATE DATABASE movie_finder_test;
GRANT ALL PRIVILEGES ON DATABASE movie_finder_test TO movie_finder;
