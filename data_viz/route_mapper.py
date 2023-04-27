import pandas as pd
import geopandas as gpd
import folium
import branca

from folium.features import GeoJsonPopup
from shapely.geometry import Point

class RouteMapper(object):

    def __init__(self, tbi_df, car_gdf, walk_gdf, bike_gdf, transit_gdf, transit_grouped_gdf, observed_gdf):
        
        # a dataframe of the processed TBI trips
        self.tbi = tbi_df
    
        # these contain the trips and the routes
        self.car = car_gdf
        self.walk = walk_gdf
        self.bike = bike_gdf
        self.transit = transit_gdf
        self.transit_grouped = transit_grouped_gdf
        self.observed = observed_gdf
    
        # Categorical color scheme for various travel modes
        self.colorMap = {
            'bike': '#00008B',      # darkblue
            'walk': '#006400',      # darkgreen
            'transit': '#4B0082',   # indigo
            'car': '#8B4513',       # saddlebrown
            'location':'#E46707'    # orange
        }

        # Object for storing attributes used to filter datasets
        self.attributeMap = {
            'Mode of route': 'mode',
            'Origin purpose': 'o_purpose',
            'Destination purpose': 'd_purpose',
            'Number of travelers': 'num_travelers',
            'Distance': 'distance',
            'Speed (MPH)': 'speed_mph',
            'VMT': 'vmt',
            'Age': 'age'
        }

        # conditions for evaluating query expressions
        self.conditions = ['==', '!=', '<', '<=', '>', '>=']
        
        
    def add_car_route(self, route_map, trip_id): 
        
        # car mode
        car_trip = self.car[self.car['trip_id']==trip_id]
        fields=['distance_meters', 'duration_seconds','weight']
        aliases=['Distance (meters)', 'Duration (sec)', 'Generalized Cost (sec)']
        car_tooltip=folium.features.GeoJsonTooltip(fields=fields, aliases=aliases)
        car_popup=folium.features.GeoJsonPopup(fields=fields, aliases=aliases)
        folium.GeoJson(car_trip, 
                       name='Car route', 
                       tooltip=car_tooltip, 
                       popup=car_popup, 
                       style_function=lambda feature: {'color':self.colorMap['car']}).add_to(route_map)
        
        return(route_map)


    def add_walk_route(self, route_map, trip_id):

        # walk mode    
        walk_trip = self.walk[self.walk['trip_id']==trip_id]
        walk_tooltip=folium.features.GeoJsonTooltip(fields=['distance_meters', 
                                                       'duration_seconds', 
                                                       'weight'],
                                               aliases=['Distance (meters)', 
                                                        'Duration (sec)', 
                                                        'Generalized Cost (sec)'])
        folium.GeoJson(walk_trip, 
                       name='Walk route', 
                       tooltip=walk_tooltip, 
                       style_function=lambda feature: {'color':self.colorMap['walk']}).add_to(route_map)
        
        return(route_map)


    def add_bike_route(self, route_map, trip_id):
        
        # bike mode
        bike_trip = self.bike[self.bike['trip_id']==trip_id]
        bike_tooltip=folium.features.GeoJsonTooltip(fields=['distance_meters', 
                                                       'duration_seconds', 
                                                       'weight'],
                                               aliases=['Distance (meters)', 
                                                        'Duration (sec)', 
                                                        'Generalized Cost (sec)'])
        folium.GeoJson(bike_trip, 
                       name='Bike route', 
                       tooltip=bike_tooltip, 
                       style_function=lambda feature: {'color':self.colorMap['bike']}).add_to(route_map)
        
        return(route_map)


    def add_transit_route(self, route_map, trip_id): 
        
        # transit mode
        transit_legs = self.transit[self.transit['trip_id']==trip_id]
        transit_leg_tooltip = {}
        for i, leg in transit_legs.iterrows(): 
            # plot the route
            transit_leg_tooltip[i] = folium.features.GeoJsonTooltip(fields=['leg_type', 
                                                                       'route_short_name', 
                                                                       'start_time_dt', 
                                                                       'end_time_dt', 
                                                                       'duration'],
                                                              aliases=['Leg Type', 
                                                                       'Start Time', 
                                                                       'End Time', 
                                                                       'Route Short Name', 
                                                                       'Duration (sec)'])
            
            folium.GeoJson(leg.geometry, 
                           name='Transit Leg', 
                           #tooltip=transit_leg_tooltip[i], 
                           style_function=lambda feature: {'color':self.colorMap['transit']}).add_to(route_map)
            
        
            # plot the first point
            folium.CircleMarker(location=[leg.geometry.coords[0][1], leg.geometry.coords[0][0]], 
                               radius=5, 
                               fill=True, 
                               color=self.colorMap['transit']).add_to(route_map)
            
            # plot the last point
            folium.CircleMarker(location=[leg.geometry.coords[-1][1], leg.geometry.coords[-1][0]],   
                               radius=5, 
                               fill=True, 
                               color=self.colorMap['transit']).add_to(route_map)
        
        return(route_map)


    def add_observed_route(self, route_map, trip_id): 
        
        # create a list of each individual lev
        trip_leg_ids_string = trip_id.replace('[','').replace(']','').split(',')
        trip_leg_ids = [int(i) for i in trip_leg_ids_string]
        
        # observed locations
        observed_points = self.observed[self.observed['trip_id'].apply(lambda x : x in trip_leg_ids)]
        for i, point in observed_points.iterrows():         
            folium.CircleMarker(location=[point.geometry.y, point.geometry.x], 
                               radius=5, 
                               fill=True, 
                               color=self.colorMap['location']).add_to(route_map)
        
        return(route_map)
                               
                               
    def set_bounds(self, route_map, trip_id): 
    
        bike_trip = self.bike[self.bike['trip_id']==trip_id]        
        route_bounds = bike_trip.bounds
        x_range = route_bounds['maxx'].values[0] - route_bounds['minx'].values[0]
        route_map.fit_bounds([[route_bounds['miny'].values[0], 
                         route_bounds['minx'].values[0]], 
                        [route_bounds['maxy'].values[0], 
                         route_bounds['maxx'].values[0] + x_range]])
        
        return(route_map)
        
    
    def create_legend_html(self, trip_id):
    
        # Header
        tbi_trip = self.tbi[self.tbi['trip_id']==trip_id].iloc[0]
        legend_html = '''
        <div style="position: fixed; 
            background-color: #FFFFFF;
            bottom: 50px; right: 50px; width: 250px; height: 430px; 
            border:2px solid grey; z-index: 9999; font-size:10px;">
            
            &nbsp;<b>Trip ID: ''' + str(trip_id) + ''' </b><br>
            &nbsp;<i class="fa fa-circle" style="color:#E46707"></i>&nbsp;Observed<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Mode: ''' + tbi_trip['mode'] + ''' <br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;O Purpose: ''' + tbi_trip['o_purpose'] + ''' <br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;D Purpose: ''' + tbi_trip['d_purpose'] + ''' <br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Num Travelers: ''' + tbi_trip['num_travelers'] + ''' <br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Age: ''' + tbi_trip['age'] + ''' <br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Day of Week: ''' + tbi_trip['travel_dow'] + ''' <br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Departure Time: ''' + tbi_trip['depart_time'] + ''' <br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Arrival Time: ''' + tbi_trip['arrive_time'] + ''' <br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Distance (mi): ''' + str(round(tbi_trip['distance'],2)) + ''' <br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Duration (min): ''' + str(tbi_trip['duration']) + ''' <br>
            '''
            
        # Walk attributes 
        walk_trip = self.walk[self.walk['trip_id']==trip_id].iloc[0]
        legend_html = legend_html + '''
            &nbsp;<i class="fa fa-circle" style="color:#006400"></i>&nbsp;Walking<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Distance (mi): ''' + str(round(walk_trip['distance_meters']/1609.34 ,2)) + '''<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Duration (min): ''' + str(round(walk_trip['duration_seconds']/60. ,2)) + '''<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Gen Cost (min): ''' + str(round(walk_trip['weight']/60. ,2)) + '''<br>
            '''
        
        # Bike attributes        
        bike_trip = self.bike[self.bike['trip_id']==trip_id].iloc[0]
        legend_html = legend_html + '''
            &nbsp;<i class="fa fa-circle" style="color:#00008B"></i>&nbsp;Biking<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Distance (mi): ''' + str(round(bike_trip['distance_meters']/1609.34 ,2)) + '''<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Duration (min): ''' + str(round(bike_trip['duration_seconds']/60. ,2)) + '''<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Gen Cost (min): ''' + str(round(bike_trip['weight']/60. ,2)) + '''<br>
            '''
        
        # car attributes        
        car_trip = self.car[self.car['trip_id']==trip_id].iloc[0]
        legend_html = legend_html + '''
            &nbsp;<i class="fa fa-circle" style="color:#8B4513"></i>&nbsp;Car<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Distance (mi): ''' + str(round(car_trip['distance_meters']/1609.34 ,2)) + '''<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Duration (min): ''' + str(round(car_trip['duration_seconds']/60. ,2)) + '''<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Gen Cost (min): ''' + str(round(car_trip['weight']/60. ,2)) + '''<br>
            '''
        
        # Transit attributes -- only if there is a valid path
        transit_trips = self.transit_grouped[self.transit_grouped['trip_id']==trip_id]
        if len(transit_trips) > 0: 
            transit_trip = transit_trips.iloc[0]
            legend_html = legend_html + '''
                &nbsp;<i class="fa fa-circle" style="color:#4B0082"></i>&nbsp;Transit<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Start Time: ''' + str(transit_trip['start_time_dt'].time()) + '''<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;End Time: ''' + str(transit_trip['end_time_dt'].time()) + '''<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Duration (min): ''' + str(round(transit_trip['duration'],2)) + '''<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Legs:''' + str(transit_trip['leg_index']) + ''' <br>
                '''
        else:
            legend_html = legend_html + '''
                &nbsp;<i class="fa fa-circle" style="color:#4B0082"></i>&nbsp;Transit<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;No Path Found<br>
                '''
            

        # Footer
        legend_html = legend_html + '''
        </div>
        '''
        
        return legend_html
    
    def map_trip(self, trip_id="Random"):
        # plot the routes on a map
        
        if trip_id=="Random":
            trip_id = self.tbi.sample(n=1)['trip_id'].iloc[0]
        trip = self.tbi[self.tbi['trip_id']==trip_id]
                    
        # instantiate a global Leaflet map object using Folium
        route_map = folium.Map(location=[44.9778,-93.2650], tiles="CartoDB positron", zoom_start=10)
        
        route_map = self.add_car_route(route_map, trip_id)
        route_map = self.add_walk_route(route_map, trip_id)
        route_map = self.add_bike_route(route_map, trip_id)
        route_map = self.add_transit_route(route_map, trip_id)
        route_map = self.add_observed_route(route_map, trip_id)

        # use branca to add legend to the map
        legend_html = self.create_legend_html(trip_id)
        legend = branca.element.Element(legend_html)
        route_map.get_root().html.add_child(legend)
        
        # set the bounds around the bike trip
        route_map = self.set_bounds(route_map, trip_id)


        # add a legend to the map
        folium.LayerControl().add_to(route_map)
        return route_map
