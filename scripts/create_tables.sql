CREATE TABLE IF NOT EXISTS locations (
   user_id INT NOT NULL,
   location_name TEXT NOT NULL,
   latitude DOUBLE PRECISION NOT NULL,
   longitude DOUBLE PRECISION NOT NULL,
   PRIMARY KEY(user_id, location_name)
);