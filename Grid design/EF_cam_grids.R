# # # Generate Camera Grid for East Foundation Survey # # #

# clear working environment
rm(list = ls())
setwd("C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/data")
# load relevant packages
library(sf)
library(tidyverse)
library(terra)
library(mapview)
library(stars)


##### FINESCALE GRID ######
setwd("C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/data")
# read in data
load("SVA_hunting_leases.rda")
# write function to run on each shapefile
generate_grid<- function(x, res) {
# make into a grid at 1km resolution
grid<- st_make_grid(x, cellsize = res)
# assign random values to grid values
my_grid <- st_sf(GridID = 1:length(grid), grid)
my_grid <- my_grid[grid,]
# rasterize the grid, and assign a 1km resolution
template = terra::rast(vect(my_grid), res = res)
# assign values to raster
ref_raster <- rasterize(vect(my_grid), template, field = "GridID")
# make raster into points
points <- terra::as.points(ref_raster, na.rm = TRUE)
# make points into sf object (because idk what's going on with terra)
pts<- st_as_sf(points)
# intersect points with original shapefile
cam_pts <- st_intersection(pts, x) 
return(cam_pts)
}
# run function
ref_pts<- generate_grid(reforma, 1000)
mesq_pts<- generate_grid(mes, 1000)
# view camera points
mapview(mesq_pts) + mapview(mes) + mapview(ref_pts) + mapview(reforma) 

# count cameras
nrow(ref_pts) + nrow(mesq_pts)
mapview(ref_pts)

# save in working directory of choice
st_write(ref_pts, "C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/output/reforma_camera_grid_locs_1000.shp",
         append = FALSE)
st_write(mesq_pts, "C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/output/muria_camera_grid_locs_1000.shp",
         append = FALSE)

###### BROADER GRID ######
# load data
ef<- st_read("C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/data/EF GIS Layers/Properties.shp")
mapview(ef)
# process data
ef_lim<- ef %>% # filter to 4 relevant properties
  filter(Ranch %in% c("ESR", "BVR", "SAV", "SRR")) %>%
  # exclude hunting lease areas
  st_difference(., mes) %>%
  st_difference(., reforma) %>%
  dplyr::select(-c(Ranch.1, Acres.1, Acres_1, Ranch.2, Acres.2, Acres_1.1))
mapview(ef_lim) # visual check
# run grid function with specific resolution
ef_pts<- generate_grid(ef_lim, 2750)
mapview(ef_pts) + mapview(ef_lim) + mapview(mesq_pts) + mapview(ref_pts) 
nrow(ef_pts)
ef_pts %>%
  group_by(Ranch) %>%
  count() %>%
  dplyr::select(-c(geometry))
# number points
SR<- ef_pts %>% 
  filter(Ranch == "SRR") %>%
  mutate(y = st_coordinates(.)[,2],
         x = st_coordinates(.)[,1]) %>%
  arrange(desc(y), x) %>%
  mutate(site = (nrow(ref_pts) + nrow(mesq_pts)) + row_number()) %>%
  dplyr::select(geometry, site)

ES<-ef_pts %>% 
               filter(Ranch == "ESR") %>%
               mutate(y = st_coordinates(.)[,2],
                      x = st_coordinates(.)[,1]) %>%
               arrange(desc(y), x) %>%
               mutate(site = (nrow(ref_pts) + nrow(mesq_pts)) + nrow(SR) + row_number()) %>%
  dplyr::select(geometry, site)
BV<- ef_pts %>% 
               filter(Ranch == "BVR") %>%
               mutate(y = st_coordinates(.)[,2],
                      x = st_coordinates(.)[,1]) %>%
               arrange(desc(y), x) %>%
               mutate(site = (nrow(ref_pts) + nrow(mesq_pts)) + nrow(SR) + nrow(ES) + row_number()) %>%
  dplyr::select(geometry, site)

SAV<- ef_pts %>% 
                filter(Ranch == "SAV") %>%
                mutate(y = st_coordinates(.)[,2],
                       x = st_coordinates(.)[,1]) %>%
                arrange(desc(y), x) %>%
                mutate(site = (nrow(ref_pts) + nrow(mesq_pts)) + nrow(SR) + nrow(ES) + nrow(BV) + row_number()) %>%
  dplyr::select(geometry, site)

mapview(SAV) + mapview(ES) + mapview(BV) + mapview(SR)

# save files
st_write(ef_pts, "C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/output/ef_grid_locs_2750.shp",
         append = FALSE)
st_write(SR, "C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/output/sr_grid_locs_2750.shp",
         append = FALSE)
st_write(ES, "C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/output/es_grid_locs_2750.shp",
         append = FALSE)
st_write(BV, "C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/output/bv_grid_locs_2750.shp",
         append = FALSE)
st_write(SAV, "C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/output/sav_grid_locs_2750.shp",
         append = FALSE)

# read in roads data
roads<- st_read("C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/data/EF Ranch Roads/Roads.shp")
# lease roads
mapview(reforma) + mapview(mes) + mapview(roads)
leases<-  st_union(reforma, mes)
indx<- roads %>%
 st_intersects(., leases, sparse = FALSE) 
mapview(roads[indx == TRUE,]) + mapview(leases)
lease_roads<- roads[indx == TRUE,]
  # combine points
lease_pts<- rbind(ref_pts, mesq_pts)
# Find the nearest line feature for each point
nearest_lines_idx <- st_nearest_feature(lease_pts, lease_roads)
# Join the points with their nearest lines
nearest_lines <- lease_roads[nearest_lines_idx, ]
# Add the IDs of the nearest lines to the points
lease_pts$nearest_line_id <- nearest_lines$id
# Calculate the actual distances (optional)
lease_pts$line_dist <- as.numeric(st_distance(lease_pts, nearest_lines, by_element = TRUE))
lease_pts <- lease_pts %>%
  mutate(x = st_coordinates(geometry)[,1],
         y = st_coordinates(geometry)[,2]) %>%
  dplyr::arrange(desc(y), x) %>%             # Sort by y (desc), then x (asc)
  mutate(site_id = row_number()) %>%       # Assign sequential numbers
  select(-c(x, y)) %>%
  mutate(cat_dist = factor(case_when(line_dist > 800 ~ "FAR",
                              line_dist >= 400 & line_dist <= 800 ~ "pretty far",
                              line_dist > 150 & line_dist < 400 ~ "not close",
                              line_dist <=150 & line_dist > 50 ~ "close",
                              line_dist <= 50 ~ "yay close"), levels = c("FAR", "pretty far", "not close", "close", "yay close")))
# check out distances
hist(lease_pts$line_dist)
# make sure site id is ordered correctly
mapview(lease_pts, zcol = "site_id") + mapview(lease_roads, color = "black")
# plot by distance from road
mapview(lease_pts, zcol = "cat_dist", col.regions = c("red", "orange", "yellow", "dark green", "green")) + mapview(lease_roads, color = "black")

mapview(lease_pts, zcol = "line_dist", col.regions = colorRampPalette(c("black", "purple", "orange", "yellow"))) + mapview(lease_roads, color = "black")

# count cameras per category
lease_pts %>%
  group_by(cat_dist) %>%
  count()

# make buffers 
lease_buff<- lease_pts %>%
  dplyr::select(site_id, line_dist, cat_dist) %>%
  st_buffer(., dist = 15)
# Create a mapview object with an ESRI basemap
mapviewOptions(basemaps = "Esri.WorldImagery")
m <- mapview(lease_pts, col.regions = c("red", "orange", "yellow", "dark green", "green"), zcol = "cat_dist") + mapview(lease_roads, color = "black")
m

# save it
setwd( "C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/Desktop/Documents/Research Projects/east_foundation_cams/output")
st_write(lease_buff, "hunting_lease_grid_buffered_15.shp", append = FALSE)
st_write(lease_roads, "hunting_lease_roads.shp")
leasePts_csv<- lease_pts %>%
  st_transform(., crs = 4326) %>%
  mutate(Lon = st_coordinates(.)[,1],
         Lat = st_coordinates(.)[,2]) %>%
  st_drop_geometry(.)
write.csv(leasePts_csv, "hunting_lease_grid_pts.csv")
