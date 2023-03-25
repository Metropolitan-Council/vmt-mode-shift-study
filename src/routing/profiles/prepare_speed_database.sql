-- These are probably not all necessary, but give the query planner maximum
-- flexibility to run efficient queries.
CREATE INDEX stl_nodes_table_latlon_idx ON stl_nodes_table (lat, lon);
CREATE INDEX stl_nodes_table_way_id_idx ON stl_nodes_table (way_id);
CREATE INDEX stl_nodes_table_seg_id_idx ON stl_nodes_table (seg_id);
CREATE INDEX stl_congestion_data_2019_seg_id_idx ON stl_congestion_data_2019 (seg_id);
