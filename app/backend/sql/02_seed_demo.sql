INSERT INTO routes (route_id, name, geom, created_at)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'Indre By Demo Loop',
    ST_GeomFromText(
        'LINESTRING(
            12.568100 55.676200,
            12.569800 55.677000,
            12.573100 55.678200,
            12.575600 55.678900,
            12.577900 55.678200,
            12.579800 55.676800,
            12.579100 55.675000,
            12.576300 55.674100,
            12.572900 55.674800,
            12.569900 55.675700,
            12.568100 55.676200
        )',
        4326
    ),
    NOW()
)
ON CONFLICT (route_id) DO NOTHING;

INSERT INTO amenities (id, category, props, geom) VALUES
    ('20000000-0000-0000-0000-000000000001', 'toilet', '{"name": "Kongens Have Toilet"}', ST_SetSRID(ST_Point(12.577200, 55.683000), 4326)),
    ('20000000-0000-0000-0000-000000000002', 'water', '{"name": "Drinking Fountain"}', ST_SetSRID(ST_Point(12.575500, 55.679900), 4326)),
    ('20000000-0000-0000-0000-000000000003', 'cafe', '{"name": "Nyhavn Espresso"}', ST_SetSRID(ST_Point(12.580800, 55.679200), 4326)),
    ('20000000-0000-0000-0000-000000000004', 'viewpoint', '{"name": "Frederiks Kirke View"}', ST_SetSRID(ST_Point(12.583000, 55.677000), 4326)),
    ('20000000-0000-0000-0000-000000000005', 'bench', '{"name": "Gammel Strand Bench"}', ST_SetSRID(ST_Point(12.577700, 55.675100), 4326)),
    ('20000000-0000-0000-0000-000000000006', 'cafe', '{"name": "Torvehallerne Coffee"}', ST_SetSRID(ST_Point(12.569200, 55.683200), 4326)),
    ('20000000-0000-0000-0000-000000000007', 'water', '{"name": "Kastellet Fountain"}', ST_SetSRID(ST_Point(12.593400, 55.691000), 4326)),
    ('20000000-0000-0000-0000-000000000008', 'bench', '{"name": "Østre Anlæg Bench"}', ST_SetSRID(ST_Point(12.576100, 55.684500), 4326)),
    ('20000000-0000-0000-0000-000000000009', 'viewpoint', '{"name": "Tårnet View"}', ST_SetSRID(ST_Point(12.573900, 55.679500), 4326)),
    ('20000000-0000-0000-0000-000000000010', 'toilet', '{"name": "Christiansborg Facilities"}', ST_SetSRID(ST_Point(12.577600, 55.676000), 4326)),
    ('20000000-0000-0000-0000-000000000011', 'water', '{"name": "Canal Tap"}', ST_SetSRID(ST_Point(12.579600, 55.674400), 4326)),
    ('20000000-0000-0000-0000-000000000012', 'cafe', '{"name": "Kayak Café"}', ST_SetSRID(ST_Point(12.584100, 55.675500), 4326)),
    ('20000000-0000-0000-0000-000000000013', 'bench', '{"name": "Nationalmuseet Rest"}', ST_SetSRID(ST_Point(12.574600, 55.673900), 4326)),
    ('20000000-0000-0000-0000-000000000014', 'viewpoint', '{"name": "Højbro Plads Lookout"}', ST_SetSRID(ST_Point(12.578800, 55.676900), 4326)),
    ('20000000-0000-0000-0000-000000000015', 'toilet', '{"name": "City Hall Toilet"}', ST_SetSRID(ST_Point(12.565900, 55.675900), 4326)),
    ('20000000-0000-0000-0000-000000000016', 'water', '{"name": "Langelinie Tap"}', ST_SetSRID(ST_Point(12.596500, 55.692500), 4326)),
    ('20000000-0000-0000-0000-000000000017', 'bench', '{"name": "Kalvebod Bølge"}', ST_SetSRID(ST_Point(12.570700, 55.669900), 4326)),
    ('20000000-0000-0000-0000-000000000018', 'cafe', '{"name": "Paper Island"}', ST_SetSRID(ST_Point(12.593200, 55.673300), 4326)),
    ('20000000-0000-0000-0000-000000000019', 'viewpoint', '{"name": "Opera Balcony"}', ST_SetSRID(ST_Point(12.600100, 55.683300), 4326)),
    ('20000000-0000-0000-0000-000000000020', 'toilet', '{"name": "Amager Torv"}', ST_SetSRID(ST_Point(12.576900, 55.679000), 4326))
ON CONFLICT (id) DO NOTHING;
