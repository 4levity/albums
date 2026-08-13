-- v17: Rename check names from *-tag to canonical names and update settings

-- First handle the special .tags -> .fields sub-key rename (single-value-tags.tags specifically)
UPDATE setting SET name='single-value-fields.fields' WHERE name='single-value-tags.tags';

UPDATE album_ignore_check SET check_name = CASE check_name
    WHEN 'album-tag' THEN 'album'
    WHEN 'artist-tag' THEN 'artist'
    WHEN 'barcode-tag' THEN 'barcode'
    WHEN 'compilation-tag' THEN 'compilation'
    WHEN 'legacy-tags' THEN 'legacy-fields'
    WHEN 'musicbrainz-tags' THEN 'musicbrainz-fields'
    WHEN 'publisher-tag' THEN 'publisher'
    WHEN 'release-country-tag' THEN 'release-country'
    WHEN 'release-type-tag' THEN 'release-type'
    WHEN 'single-value-tags' THEN 'single-value-fields'
END
WHERE check_name = 'album-tag' OR check_name = 'artist-tag' OR check_name = 'barcode-tag' OR check_name = 'compilation-tag' OR check_name = 'legacy-tags' OR check_name = 'musicbrainz-tags' OR check_name = 'publisher-tag' OR check_name = 'release-country-tag' OR check_name = 'release-type-tag' OR check_name = 'single-value-tags';

UPDATE setting SET name = REPLACE(name, 'album-tag.', 'album.') WHERE name LIKE 'album-tag.%';
UPDATE setting SET name = REPLACE(name, 'artist-tag.', 'artist.') WHERE name LIKE 'artist-tag.%';
UPDATE setting SET name = REPLACE(name, 'barcode-tag.', 'barcode.') WHERE name LIKE 'barcode-tag.%';
UPDATE setting SET name = REPLACE(name, 'compilation-tag.', 'compilation.') WHERE name LIKE 'compilation-tag.%';
UPDATE setting SET name = REPLACE(name, 'legacy-tags.', 'legacy-fields.') WHERE name LIKE 'legacy-tags.%';
UPDATE setting SET name = REPLACE(name, 'musicbrainz-tags.', 'musicbrainz-fields.') WHERE name LIKE 'musicbrainz-tags.%';
UPDATE setting SET name = REPLACE(name, 'publisher-tag.', 'publisher.') WHERE name LIKE 'publisher-tag.%';
UPDATE setting SET name = REPLACE(name, 'release-country-tag.', 'release-country.') WHERE name LIKE 'release-country-tag.%';
UPDATE setting SET name = REPLACE(name, 'release-type-tag.', 'release-type.') WHERE name LIKE 'release-type-tag.%';
UPDATE setting SET name = REPLACE(name, 'single-value-tags.', 'single-value-fields.') WHERE name LIKE 'single-value-tags.%';
