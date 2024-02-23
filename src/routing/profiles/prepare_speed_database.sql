-- These are probably not all necessary, but give the query planner maximum
-- flexibility to run efficient queries.
CREATE INDEX stl_nodes_table_latlon_idx ON stl_nodes_table (lat, lon);
CREATE INDEX stl_nodes_table_way_id_idx ON stl_nodes_table (way_id);
CREATE INDEX stl_nodes_table_seg_id_idx ON stl_nodes_table (seg_id);
CREATE INDEX stl_congestion_data_2019_seg_id_idx ON stl_congestion_data_2019 (seg_id);

-- Rename all the weekday columns to remove typo

ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_0-6" TO "weekdays_0-6";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_6-7" TO "weekdays_6-7";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_7-8" TO "weekdays_7-8";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_8-9" TO "weekdays_8-9";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_9-10" TO "weekdays_9-10";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_10-11" TO "weekdays_10-11";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_11-12" TO "weekdays_11-12";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_12-13" TO "weekdays_12-13";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_13-14" TO "weekdays_13-14";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_14-15" TO "weekdays_14-15";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_15-16" TO "weekdays_15-16";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_16-17" TO "weekdays_16-17";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_17-18" TO "weekdays_17-18";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_18-19" TO "weekdays_18-19";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_19-20" TO "weekdays_19-20";
ALTER TABLE stl_congestion_data_2019 RENAME COLUMN "weedays_20-24" TO "weekdays_20-24";