#! /bin/bash

  export SPEED_DATABASE="/streetlight_data.db"
  # echo ".schema stl_congestion_data_2019" |
  #    sqlite3 "$SPEED_DATABASE" |
  #    grep REAL |
  #   sed -E 's/^ +"([^"]+).*$/\1/' |
  #  xargs -n 1 -Icol env SPEED_COLUMN=col bash build_street_network.sh ~/vmt-networks/analysis-area.osm.pbf profiles/car_traffic.lua ~/vmt-networks/car_col

  ./_build_street_network.sh ~/vmt-networks/analysis-area.osm.pbf profiles/foot_lts.lua ~/vmt-networks/walk-lts
  ./_build_street_network.sh ~/vmt-networks/analysis-area.osm.pbf profiles/bicycle_lts.lua ~/vmt-networks/bike-lts

