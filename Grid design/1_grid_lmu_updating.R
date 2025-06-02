# # # Considering LMU's # # #

# clear working environment
rm(list = ls())
setwd("C:/Users/kukwh001/OneDrive - Texas A&M University - Kingsville/East Camera Study")
# load relevant packages
library(sf)
library(tidyverse)
library(terra)
library(mapview)
library(stars)
`%!in%`<- Negate('%in%')
##### FINESCALE GRID ######
# read in data
load("data/SVA_hunting_leases.rda")
load("hunting_lease_grids.rda")
gps<- read.table("data/Cumulative_D_8508_2025318500.txt", sep = ",", header = T)
# LMU's
lmu<- st_read("data/Draft_LMU_PenaReformaChapoteMuralla.shp") %>%
  st_make_valid(.) %>%
  st_transform(., crs = 26914) %>%
  mutate(covered = ifelse(Name %in% c("Chapote", "Corrales Prietas"), "no", "yes"),
         Acres = as.numeric(st_area(.) * 0.000247105),
         ID = seq(from = 1, to = nrow(.), by = 1))

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
# rerun grid generating function
ref_pts<- generate_grid(reforma, 1000) # 1km resolution between cameras
mesq_pts<- generate_grid(mes, 1000)
# view camera points relative to LMU's
mapview(lmu, zcol = "Name") + mapview(mesq_pts, col.regions = "green") + mapview(ref_pts, col.regions = "green") 
mapview(reforma, col.regions = "grey") + mapview(mes, col.regions = "grey") + mapview(lmu, zcol = "covered", col.regions = c("darkred", "darkgreen")) + mapview(ref_pts, col.regions = "green") + mapview(mesq_pts, col.regions = "green") 

lmu %>%
  st_join(., ref_pts, st_intersects) %>%
  st_join(., mesq_pts, st_intersects) %>%
  group_by(ID) %>%
  count() %>%
  summarize(mean(n))
# if we wanted to add cameras to the other grid...
# try to generate points in middling area along and see how it overlaps with grid
mid <- lmu %>% 
  filter(covered == "no") 
mid_pts<- generate_grid(mid, 1000)
nrow(mid_pts) # 30 additional cameras (add this info to budget)
mapview(reforma, col.regions = "grey") + mapview(mes, col.regions = "grey") + mapview(lmu, zcol = "Name") + mapview(ref_pts) + mapview(mesq_pts) + mapview(mid_pts)
# try regenerating points
try<- mid %>%
  st_combine(.) %>%
  st_union(., reforma, by_feature = TRUE) %>%
  st_union(., mes)
mid_pts<- generate_grid(try, 1000)
mapview(mid_pts, col.regions = "grey") + mapview(ref_pts) + mapview(mesq_pts) + mapview(mes) + mapview(reforma) + mapview(st_combine(mid)) + mapview(lmu)
  # shows a mismatch

# try regenerating grid with just mesquite and esperanza LMU instead of polygon
lmu_north<- lmu %>%
  filter(Name %in% c("Mesquite", "Esperanza")) %>%
  st_combine(.)
try2<- mid %>%
  st_combine(.) %>%
  st_union(., reforma, by_feature = TRUE) %>%
  st_union(., lmu_north)
mid_pts<- generate_grid(try2, 1000)
mapview(mid_pts) + mapview(ref_pts) + mapview(lmu)
# shows a mismatch

# try snapping cameras on
# Combine your existing grid points (assuming sf POINT objects)
all_existing_points <- rbind(ref_pts, mesq_pts)  # both are sf objects
# Get bounding box of the combined grid
bbox <- st_bbox(all_existing_points)
# Define raster/grid origin — lower left corner of the bounding box
origin <- c(floor(bbox["xmin"]), floor(bbox["ymin"]))
library(terra)
# Create a raster template that spans the union of all 3 polygons
combined_poly <- st_union(reforma, mes, mid)
ext <- ext(combined_poly)
# Make 1km raster grid with matching origin
r <- rast(ext, resolution = 1000)
origin_diff <- origin - c(xmin(r), ymin(r))
r <- shift(r, dx = origin_diff[1], dy = origin_diff[2])
# Convert to points
r_points <- as.points(r)
# Keep only those in the middle polygon
r_points_sf <- st_as_sf(r_points)
r_points_mid <- r_points_sf[st_within(r_points_sf, mid, sparse = FALSE), ]

# plot gps data
gps_utm<- gps %>%
  filter(!is.na(Latitude)) %>%
  filter(!is.na(Longitude)) %>%
  mutate(Date = as.Date(Date)) %>%
  mutate(CollarSerialNumber = ifelse(CollarSerialNumber == 57877 & Date > as.Date("2025-04-01"),
         578777, CollarSerialNumber)) %>%
  filter(!(CollarSerialNumber == 57877 & Date > as.Date("2025-03-05"))) %>%
  st_as_sf(., coords = c("Longitude", "Latitude"), crs = 4326) %>%
  st_transform(crs(mesq_pts)) %>%
  mutate(CollarSerialNumber = as.factor(CollarSerialNumber))
gps_utm$Minute <- sprintf("%02d", gps_utm$Minute)
gps_utm$Hour <- sprintf("%02d", gps_utm$Hour)

library(amt)
big_polyg<- st_union(lmu, reforma) %>%
  st_union(., mes) %>%
  st_buffer(., dist = 10000) 
mapview(big_polyg)

intersect_idx <- st_intersects(gps_utm, big_polyg, sparse = FALSE)
gps_utm<- gps_utm[intersect_idx[,1], ]

mcps<- gps_utm %>%
  mutate(x = st_coordinates(.)[,1],
         y = st_coordinates(.)[,2]) %>%
  st_drop_geometry(.) %>%
  mutate(timestamp = as.POSIXct(paste(Date, paste(Hour, Minute, sep = ":"))), 
         format = "%Y-%m-%d %H:%M", tz = "GMT") %>%
  make_track(x, y, timestamp, id = CollarSerialNumber,
             crs = 26914, all_cols = TRUE) %>%
  nest(track = -"CollarSerialNumber") %>%
  arrange(CollarSerialNumber) %>%
  mutate(
    smpl = map(track, ~ track_resample(., rate = minutes(180), tolerance = minutes(30)))
  ) %>%
  mutate(
    mcp = map(smpl, ~hr_mcp(.))
  )
mcp_sf <- mcps %>%
  select(CollarSerialNumber, mcp) %>%
  mutate(iso = map(mcp, hr_isopleths)) %>%  # get polygons
  # bind all iso outputs while adding ID
  mutate(iso = map2(iso, CollarSerialNumber, ~mutate(.x, id = .y))) %>%
  pull(iso) %>%
  bind_rows()
mean(st_area(mcp_sf))

mapview(lmu) + mapview(mcp_sf, zcol = "id")

mcp_sf %>%
  st_join(., lmu, st_intersects) %>%
  group_by(id) %>%
  count() %>%
  summarize(mean(n))

#what's the deer density on SAV; in this area what do they assume it is; acres/deer; how many deer in 2000
# acre block; how many blocks can we have; only have money to treat 1000/2000 acres, so units not
# treated 100% (90-50% brush); how many are they gonna treat how many replicates, do we need more 
# collars and cameras to sample appropriately. If we were gonna have a whole other grid or expand
# what's the rate of LMU included as we scale out. 

# Densities ranged from 15-25 acres/deer between 2014-2022, about 22.22 on average

## designating treatment areas
mapview(lmu, zcol = "ID")
# Distance threshold in meters (e.g., 10–50 m depending on gap spacing)
buffer_dist <- 50
# Compute neighbors within buffer distance
neighbors <- st_is_within_distance(lmu, dist = buffer_dist)
adj_df <- tibble(
  ID = rep(seq_along(neighbors), lengths(neighbors)),
  neighbor_id = unlist(neighbors)
) %>%
  filter(ID != neighbor_id)
# generate potential samples
set.seed(42)
# loop built to maximize selecting LMU's across entire space,
  # while avoiding neighboring LMU's
best_selection <- function(polys, adj_df, n_iter = 100) {
  best_ids <- c()
  best_total_area <- 0
  
  for (i in 1:n_iter) {
    set.seed(i)
    # Shuffle, but favor large LMUs by sorting first
    shuffled <- polys %>% 
      arrange(desc(Acres)) %>% 
      slice_sample(prop = 1)  # randomize order while still biased to large
    
    selected <- c()
    
    for (candidate in shuffled$ID) {
      is_neighbor <- any(
        adj_df$ID == candidate & adj_df$neighbor_id %in% selected |
          adj_df$neighbor_id == candidate & adj_df$ID %in% selected
      )
      if (!is_neighbor) {
        selected <- c(selected, candidate)
      }
    }
    
    total_area <- sum(polys$Acres[polys$ID %in% selected])
    
    if (total_area > best_total_area) {
      best_total_area <- total_area
      best_ids <- selected
    }
  }
  
  return(best_ids)
}
selected_ids <- best_selection(lmu, adj_df, n_iter = 200)
polys_selected <- lmu %>% filter(ID %in% selected_ids)
mapview(polys_selected)
# function to (1) spread treatments across total area, (2) maximize overall spread per treatment
assign_treatments_with_cluster_penalty <- function(sf_polys, id_col = "ID", n_treatments = 4, min_spacing = 400) {
  stopifnot(inherits(sf_polys, "sf"))
  treatments <- c("control", "supplemental feed", "vegetation removal", "feed + removal")
  
  sf_polys <- sf_polys %>%
    mutate(
      !!id_col := as.character(.data[[id_col]]),
      area = as.numeric(st_area(geometry)),
      treatment = NA_character_,
      centroid = st_centroid(geometry)
    )
  
  treatment_totals <- setNames(rep(0, n_treatments), treatments)
  
  # Sort by descending area to assign larger LMUs first
  to_assign <- sf_polys %>%
    st_drop_geometry() %>%
    arrange(desc(area)) %>%
    mutate(!!id_col := as.character(.data[[id_col]]))
  
  for (i in seq_len(nrow(to_assign))) {
    current_id <- to_assign[[id_col]][i]
    row_index <- match(current_id, sf_polys[[id_col]])
    current_centroid <- sf_polys$centroid[row_index]
    
    scores <- sapply(treatments, function(t) {
      already_assigned <- sf_polys %>% filter(!is.na(treatment))
      same_group <- already_assigned %>% filter(treatment == t)
      
      if (nrow(same_group) == 0) return(1e6)  # prioritize empty groups
      
      # Distance to same treatment
      dist_same <- st_distance(current_centroid, st_centroid(same_group$geometry)) %>% as.numeric()
      min_dist_same <- ifelse(length(dist_same) > 0, min(dist_same), Inf)
      
      # Distance to all treatments
      dist_all <- st_distance(current_centroid, st_centroid(already_assigned$geometry)) %>% as.numeric()
      min_dist_all <- ifelse(length(dist_all) > 0, min(dist_all), Inf)
      
      # Penalize heavily if same treatment is nearby
      if (min_dist_same < min_spacing) return(-Inf)
      
      # Soft penalty if any treatment is nearby (encourages spread)
      cluster_penalty <- ifelse(min_dist_all < min_spacing, -5000, 0)
      
      # Area penalty (less weight than distance)
      area_penalty <- treatment_totals[t] / 1000
      
      score <- min_dist_same - area_penalty + cluster_penalty
      return(score)
    })
    
    if (all(is.infinite(scores))) {
      warning(paste("Could not assign polygon", current_id, "- all treatments too close"))
      next
    }
    
    best_treatment <- treatments[which.max(scores)]
    sf_polys$treatment[row_index] <- best_treatment
    treatment_totals[best_treatment] <- treatment_totals[best_treatment] + to_assign$area[i]
  }
  
  sf_polys <- sf_polys %>% select(-centroid)
  return(sf_polys)
}

# run function
polys_treated <- assign_treatments_with_cluster_penalty(polys_selected, id_col = "ID", n_treatments = 4, min_spacing = 400) %>%
  mutate(treatment = factor(treatment, levels = c("control", "supplemental feed", "vegetation removal", "feed + removal")))
# look at relative areas and spread
polys_treated %>%
  group_by(treatment) %>%
  summarise(
    count = n(),
    total_area = sum(st_area(geometry)) * 0.000247105,
    centroid_spread = mean(st_distance(st_centroid(geometry))[lower.tri(diag(n()))])
  )
# Join treatment results back into full polygon set
full_polys <- lmu %>%
  left_join(polys_treated %>% st_drop_geometry() %>% dplyr::select(ID, treatment) %>% mutate(ID = as.numeric(ID)), by = "ID") %>%
  mutate(treatment = factor(if_else(is.na(treatment), "buffer", treatment), levels = c("buffer", "control", "supplemental feed",
                                                                                       "vegetation removal", "feed + removal")))
# Plot with gray buffers and colored treatments
ggplot(full_polys) +
  geom_sf(aes(fill = treatment), color = "white", size = 0.2) +
  scale_fill_manual(
    values = c(
      "control" = "green4",
      "supplemental feed" = "goldenrod",
      "vegetation removal" = "darkred",
      "feed + removal" = "pink2",
      "buffer" = "grey80"
    )  ) +
  theme_minimal() +
  guides(fill = guide_legend(title = "Treatment"))

# post hoc processing if imbalanced area
# Check the supplemental feed LMUs
supp_feed <- polys_treated %>% filter(treatment == "supplemental feed") %>% arrange(desc(st_area(geometry)))
# Check their neighbors or distances to vegetation removal blocks
veg_removal <- polys_treated %>% filter(treatment == "vegetation removal")
st_crs(veg_removal) <- st_crs(supp_feed)
# Vectorized distance matrix: 4 (supp) x 3 (veg)
dist_matrix <- st_distance(supp_feed, veg_removal)
# Get minimum distance from each supp_feed row to any veg_removal polygon
supp_feed$min_dist_to_veg_removal <- apply(dist_matrix, 1, min)
# Now sort
supp_feed <- supp_feed %>% arrange(min_dist_to_veg_removal)
# assign
best_id <- supp_feed$ID[4]
# update
full_polys <- full_polys %>%
  mutate(treatment = case_when(
    ID == best_id ~ "vegetation removal",
    TRUE ~ treatment),
    treatment = factor(treatment, levels = c("buffer", "control", "supplemental feed", "vegetation removal", "feed + removal")))
ggplot(full_polys) +
  geom_sf(aes(fill = treatment), color = "white", size = 0.2) +
  scale_fill_manual(
    values = c(
      "control" = "green4",
      "supplemental feed" = "goldenrod",
      "vegetation removal" = "darkred",
      "feed + removal" = "pink2",
      "buffer" = "grey80"
    )  ) +
  theme_minimal() +
  guides(fill = guide_legend(title = "Treatment"))
# recalculate area
full_polys %>%
  filter(treatment != "buffer") %>%
  group_by(treatment) %>%
  summarise(
    count = n(),
    total_area = sum(st_area(geometry)) * 0.000247105,
    centroid_spread = mean(st_distance(st_centroid(geometry))[lower.tri(diag(n()))])
  )
# Calculate total area
spray_polys<- full_polys %>% filter(treatment %in% c("vegetation removal", "feed + removal"))
total_acres <- sum(spray_polys$Acres, na.rm = TRUE)
# Proportional allocation
spray_polys$SprayedAcres <- (spray_polys$Acres / total_acres) * 1000
# Optional: round to 2 decimal places
spray_polys$SprayedAcres <- round(spray_polys$SprayedAcres, 2)
# Check that total sprayed area = 1000
sum(spray_polys$SprayedAcres)

ggplot(full_polys) +
  geom_sf(aes(fill = treatment), color = "white", size = 0.2) +
  scale_fill_manual(
    values = c(
      "control" = "green4",
      "supplemental feed" = "green3",
      "vegetation removal" = "darkred",
      "feed + removal" = "red3",
      "buffer" = "grey80"
    )  ) +
  theme_minimal() +
  guides(fill = guide_legend(title = "Treatment"))

#### simulation reps #####

library(lme4)
library(simr)

# Simulate a basic dataset
set.seed(42)
# === SETUP ===
simulate_factorial_dataset <- function(n_lmus = 14, n_obs = 90,
                                       effect_feed = 0.5, 
                                       effect_veg = 1.0, 
                                       interaction = 0.5) {
  # 4 LMUs per treatment group (ideally)
  treatment_combos <- expand.grid(feed = c(0, 1), veg = c(0, 1))  # 4 groups
  treatment_combos$group <- paste0("G", 1:4)
  
  lmu_per_group <- floor(n_lmus / 4)
  lmu_ids <- paste0("L", 1:(lmu_per_group * 4))
  
  # Assign LMUs to treatments
  LMU_assignments <- data.frame(
    LMU = lmu_ids,
    feed = rep(treatment_combos$feed, each = lmu_per_group),
    veg = rep(treatment_combos$veg, each = lmu_per_group)
  )
  
  df <- expand.grid(
    LMU = LMU_assignments$LMU,
    day = 1:n_obs
  ) %>%
    left_join(LMU_assignments, by = "LMU") %>%
    mutate(
      mu = 4 + 
        effect_feed * feed +
        effect_veg * veg +
        interaction * (feed * veg),
      deer = rpois(n(), lambda = mu)
    )
  
  return(df)
}

# === FUNCTION TO TEST POWER FOR A GIVEN CONTRAST ===
run_factorial_power_test <- function(df, nsim = 100) {
  model <- glmer(deer ~ feed * veg + (1 | LMU),
                 data = df, family = poisson())
  
  model_sim <- extend(model, along = "LMU", n = length(unique(df$LMU)))
  
  list(
    feed = powerSim(model_sim, nsim = nsim, test = fixed("feed", "z")),
    veg = powerSim(model_sim, nsim = nsim, test = fixed("veg", "z")),
    interaction = powerSim(model_sim, nsim = nsim, test = fixed("feed:veg", "z"))
  )
}
# -- diff effect sizes --
effect_scenarios <- list(
  small = c(feed = 0.3, veg = 0.3, interaction = 0.2),
  medium = c(feed = 0.5, veg = 0.6, interaction = 0.5),
  large = c(feed = 1.0, veg = 0.8, interaction = 1.0)
)
results <- list()

for (label in names(effect_scenarios)) {
  eff <- effect_scenarios[[label]]
  df <- simulate_factorial_dataset(effect_feed = eff["feed"],
                                   effect_veg = eff["veg"],
                                   interaction = eff["interaction"])
  results[[label]] <- run_factorial_power_test(df, nsim = 500)
}
# Flatten results into long format
power_df <- purrr::map_dfr(
  names(results),
  function(effect_label) {
    res <- results[[effect_label]]
    
    tibble::tibble(
      effect = c("feed", "veg", "interaction"),
      power = c(res$feed$x / res$feed$n,
                res$veg$x / res$veg$n,
                res$interaction$x / res$interaction$n),
      lower = c(res$feed$conf.int[1],
                res$veg$conf.int[1],
                res$interaction$conf.int[1]),
      upper = c(res$feed$conf.int[2],
                res$veg$conf.int[2],
                res$interaction$conf.int[2]),
      effect_label = effect_label
    )
  }
)
effect_sizes <- list(
  small = c(feed = 0.3, veg = 0.4, interaction = 0.2),
  medium = c(feed = 0.5, veg = 1.0, interaction = 0.5),
  large = c(feed = 1.0, veg = 1.5, interaction = 1.0)
)
power_df <- power_df %>%
  rowwise() %>%
  mutate(effect_size = effect_sizes[[effect_label]][effect])
# plot it
ggplot(power_df, aes(x = effect_size, y = power, color = effect)) +
  geom_line() +
  geom_point(size = 3) +
  geom_hline(yintercept = 0.8, linetype = "dashed", color = "gray40") +
  scale_y_continuous(labels = scales::percent_format(), limits = c(0, 1)) +
  labs(
    title = "Power Analysis for Factorial Treatment Effects",
    subtitle = "Dashed line = 80% power threshold",
    x = "Effect Size",
    y = "Power",
    color = "Effect"
  ) +
  theme_minimal()


######### grid

# Assuming 'lmu_union' is your spatial object
lmu_union <- st_union(lmu) # Replace with appropriate CRS
# Convert the grid to an sf object
p2<- lmu %>% 
  filter(Name %in% c("Chapote", "Corrales Prietas")) %>%
  mutate(pasture = "mid") %>%
  st_union() %>%
  st_as_sf() %>%
  mutate(pasture = "mid") %>%
  rename(geometry = x)
p1<- mes %>% mutate(pasture = "mes") %>% dplyr::select(c(pasture))
p3<- reforma %>% mutate(pasture = "ref") %>% dplyr::select(c(pasture))
polygons_sf<- rbind(p1, p2, p3)
mapview(polygons_sf)

# Step 1: Get convex hull (or concave hull if needed)
hull <- p1 %>% 
  st_cast("MULTIPOLYGON") %>%
  st_union() %>%
  st_convex_hull()

# Step 2: Get oriented bounding box via concaveman (returns a rectangle)
obb <- concaveman::get_minimum_bounding_rectangle(hull)








# 1. Calculate areas and required minimums
min_cells <- data.frame(
  pasture = c("mes", "mid", "ref"),
  min_cells = c(4, 4, 8)
)

pasture_areas <- polygons_sf %>%
  mutate(area = as.numeric(st_area(.))) %>%
  left_join(min_cells, by = "pasture") %>%
  mutate(max_cell_area = area / min_cells)

# 2. Determine limiting cell size
target_cell_area <- min(pasture_areas$max_cell_area)
cell_width <- sqrt(target_cell_area) # about 2.5km

# 3. Build a grid across the union of all pastures
grid1 <- st_make_grid(p1,
                     cellsize = 2000,
                     square = TRUE) %>%
  st_sf() %>%
  st_intersection(., p1) %>%
  mutate(intersect_area = st_area(.)) %>%
  mutate(cell_area = 2000^2) %>%
  filter(as.numeric(intersect_area) >= 0.9 * cell_area)
grid2 <- st_make_grid(p2,
                      cellsize = 2000,
                      square = TRUE) %>%
  st_sf() %>%
  st_intersection(., p2) %>%
  mutate(intersect_area = st_area(.)) %>%
  mutate(cell_area = 2000^2) %>%
  filter(as.numeric(intersect_area) >= 0.9 * cell_area)
grid3 <- st_make_grid(p3,
                      cellsize = 2000,
                      square = TRUE) %>%
  st_sf() %>%
  st_intersection(., p3) %>%
  mutate(intersect_area = st_area(.)) %>%
  mutate(cell_area = 2000^2) %>%
  filter(as.numeric(intersect_area) >= 0.9 * cell_area)


mapview(grid1) + mapview(grid2) + mapview(grid3) + mapview(polygons_sf)

# 4. Intersect grid with each pasture and keep only fully covered cells
grids_list <- lapply(unique(polygons_sf$pasture), function(pasture_name) {
  pasture_poly <- polygons_sf %>% filter(pasture == pasture_name)
  grid_clipped <- st_intersection(grid, pasture_poly)
  
  # Keep only cells that are mostly within the pasture (≥90%)
  grid_clipped <- grid_clipped %>%
    mutate(intersect_area = st_area(.)) %>%
    mutate(cell_area = cell_width^2) %>%
    filter(as.numeric(intersect_area) >= 0.9 * cell_area) %>%
    mutate(pasture = pasture_name)
})

# 5. Combine grids
grid_final <- do.call(rbind, grids_list)

mapview(grid_final, zcol = "pasture") + mapview(polygons_sf, alpha = 0.3)



t<- make_grid_cells(polygons_sf[2,], 4)
mapview(t) + mapview(polygons_sf[2,])


cell_plan <- data.frame(
  pasture = c("mes", "mid", "ref"),
  n_cells = c(4, 4, 8)
)

st_write(obj = p1, dsn = "mes_polygons.shp")
st_write(obj = p2, dsn = "mid_polygons.shp")
st_write(obj = p3, dsn = "ref_polygons.shp")

make_grid_cells <- function(polygon, n_cells) {
  # Get total area
  total_area <- st_area(polygon)
 
  
  # Estimate cell width for square-ish cells
  cell_width <-2000
  
  # Create grid for bounding box of the polygon
  grid <- st_make_grid(polygon, cellsize = cell_width, square = TRUE)
  
  # Intersect grid with pasture polygon and keep only well-covered ones
  grid_clipped <- st_intersection(st_sf(geometry = grid), polygon)
  
  # (Optional) Select n_cells closest in area to the target
  grid_clipped <- grid_clipped %>%
    mutate(area = st_area(geometry)) %>%
    slice_min(abs(as.numeric(area) - target_cell_area), n = n_cells)
  
  return(grid_clipped)
}

# Merge pasture info
polygons_sf <- left_join(polygons_sf, cell_plan, by = "pasture")
make_grid_cells(polygons_sf[1,], 4)

# Loop over pastures
grids_list <- polygons_sf %>%
  group_split(pasture) %>%
  lapply(function(p) {
    make_grid_cells(p, p$n_cells[1]) %>%
      mutate(pasture = p$pasture[1])
  })

# Combine all grids
grid_final <- do.call(rbind, grids_list)
st_area(grid_final)
mapview(grid_final) + mapview(polygons_sf)






# Create a grid with 1.5 km x 1.5 km cells
grid <- st_make_grid(
  lmu_union,
  cellsize = c(1500, 1500),  # 1.5 km in meters
  what = "polygons",
  square = TRUE
)


# Rotate full geometry using affine transform
rotate_sf <- function(sf_obj, angle_rad, center) {
  rot_mat <- matrix(c(cos(angle_rad), sin(angle_rad), -sin(angle_rad), cos(angle_rad)), nrow = 2)
  st_geometry(sf_obj) <- st_geometry(sf_obj) %>%
    st_coordinates() %>%
    as_tibble() %>%
    group_split(L1) %>%
    lapply(function(coords) {
      rotated <- (as.matrix(coords[, c("X", "Y")]) - center) %*% rot_mat + center
      st_polygon(list(rotated))
    }) %>%
    st_sfc(crs = st_crs(sf_obj))
  sf_obj
}

# Get top edge angle
get_top_edge_angle <- function(poly) {
  coords <- st_coordinates(poly)
  coords <- coords[coords[, "L1"] == 1, , drop = FALSE]  # outer ring
  top_y <- max(coords[, "Y"])
  top_coords <- coords[abs(coords[, "Y"] - top_y) < 5, , drop = FALSE]
  
  if (nrow(top_coords) < 2) return(0)
  pt1 <- top_coords[1, 1:2]
  pt2 <- top_coords[nrow(top_coords), 1:2]
  atan2(pt2[2] - pt1[2], pt2[1] - pt1[1])
}

# Main grid creation function
make_oriented_grid <- function(poly_sf, cellsize = 1750) {
  poly_geom <- st_geometry(poly_sf)
  angle <- get_top_edge_angle(poly_geom)
  center <- st_coordinates(st_centroid(poly_geom))[1, ]
  
  # Rotate polygon flat
  rot_mat <- matrix(c(cos(-angle), sin(-angle), -sin(-angle), cos(-angle)), 2)
  poly_rot <- (st_geometry(poly_sf) - center) * rot_mat + center
  st_geometry(poly_sf) <- poly_rot
  
  # Grid over bbox of rotated polygon
  grid_rot <- st_make_grid(poly_sf, cellsize = cellsize, what = "polygons", square = TRUE)
  grid_sf <- st_sf(cell_id = seq_along(grid_rot), geometry = grid_rot)
  
  # Intersect and filter 75% coverage
  clipped <- st_intersection(grid_sf, poly_sf)
  clipped$grid_area <- st_area(grid_sf)[clipped$cell_id]
  clipped$clip_area <- st_area(clipped)
  clipped <- clipped[as.numeric(clipped$clip_area / clipped$grid_area) >= 0.75, ]
  clipped$pasture <- poly_sf$pasture[1]
  
  # Rotate grid cells back
  rot_back <- matrix(c(cos(angle), sin(angle), -sin(angle), cos(angle)), 2)
  st_geometry(clipped) <- (st_geometry(clipped) - center) * rot_back + center
  
  return(clipped)
}

# polygons_sf: your 3-polygon sf with 'pasture' column
grids <- lapply(1:nrow(polygons_sf), function(i) {
  make_oriented_grid(polygons_sf[i, ])
})
grid_final <- do.call(rbind, grids)
st_crs(grid_final)<- st_crs(polygons_sf)
# Sanity check
print(class(grid_final))  # should be "sf"
mapview(grid_final) + mapview(polygons_sf, alpha = 0.2)
# Extract shrub
grid_vect <- vect(grid_final)
shrub_vals <- terra::extract(shrub_raster, grid_vect, fun = mean, na.rm = TRUE)
grid_final$mean_shrub <- shrub_vals[, 2]
# Classify
grid_final <- grid_final %>%
  mutate(
    shrub_group = factor(case_when(
      mean_shrub >= quantile(mean_shrub, 0.66, na.rm = TRUE) ~ "high",
      mean_shrub <= quantile(mean_shrub, 0.33, na.rm = TRUE) ~ "low",
      TRUE ~ "mid"
    ), levels = c("low", "mid", "high")
  ))
mapview(grid_final, zcol = "shrub_group")
# Random treatment
set.seed(42)
treatments <- c("control", "feed", "veg", "both")
assign_even_treatments <- function(df_group) {
  n <- nrow(df_group)
  reps <- rep(treatments, length.out = n)
  df_group$treatment <- sample(reps)
  return(df_group)
}

grid_t <- grid_final %>%
  group_by(shrub_group) %>%
  group_modify(~assign_even_treatments(.x)) %>%
  ungroup() %>%
  st_as_sf() %>%
  mutate(treatment = factor(treatment, levels = c("control", "feed", "veg", "both")))

mapview(grid_t, zcol = "treatment")

# Define colors
library(RColorBrewer)
library(leaflet)
# Custom color mappings
treatment_colors <- c(
  T1 = "#666666",    # gray
  T2 = "#377eb8",    # blue
  T3 = "#4daf4a",    # green
  T4 = "#984ea3"     # purple
)

shrub_colors <- c(
  low = "yellow",
  mid = "orange",
  high = "deeppink"
)
treatment_palette <- colorFactor(treatment_colors, domain = grid_final$treatment)
shrub_palette <- colorFactor(shrub_colors, domain = grid_final$shrub_group)

# Build map
leaflet() %>%
  # Satellite base layer
  addProviderTiles("Esri.WorldImagery") %>%
  
  # Optional: add pasture polygons underneath
  addPolygons(data = polygons_sf %>% st_transform(., crs = 4326),
              fillColor = "white",  # or NA if you want only outlines
              fillOpacity = 0.2,
              color = "black",
              weight = 1,
              label = ~pasture,
              group = "Pasture Boundaries") %>%
  
  # Add treatment grid with shrub group borders
  addPolygons(data = grid_t %>% st_transform(., crs = 4326),
              fillColor = ~treatment_palette(treatment),
              color = ~shrub_palette(shrub_group),
              weight = 2,
              opacity = 1,
              fillOpacity = 0.6,
              label = ~paste("Shrub:", shrub_group, "<br>Treatment:", treatment),
              group = "Treatment Grid") %>%
  
  # Legends
  addLegend("bottomright", pal = treatment_palette, values = grid_final$treatment,
            title = "Treatment", opacity = 1) %>%
  addLegend("bottomleft", pal = shrub_palette, values = grid_final$shrub_group,
            title = "Shrub Group (border)", opacity = 1)

# option 2: buffered assignmetn
north<- c(6, 12, 8, 14)
mid<- c(13, 7, 9, 3)
south<- c(22, 19, 14, 9, 11, 6)

test<- grid_final %>%
  mutate(treated = case_when(cell_id %in% north & pasture == "mes" ~ "treatment",
                             cell_id %in% mid & pasture == "mid" ~ "treatment",
                             cell_id %in% south & pasture == "ref" ~ "treatment",
                             TRUE ~ "buffer"
  )) 
st_crs(test)<- st_crs(polygons_sf)
# Extract shrub
grid_vect <- vect(test)
shrub_vals <- terra::extract(shrub_raster, grid_vect, fun = mean, na.rm = TRUE)
test$mean_shrub <- shrub_vals[, 2]
test<- test %>%
  mutate(
    shrub_group = factor(case_when(
      mean_shrub >= quantile(mean_shrub, 0.66, na.rm = TRUE) ~ "high",
      mean_shrub <= quantile(mean_shrub, 0.33, na.rm = TRUE) ~ "low",
      TRUE ~ "mid"
    ), levels = c("low", "mid", "high")
    ))
mapview(test, zcol = "shrub_group")
# Custom color mappings

test<- test %>%
  mutate(shrub_treatment = paste(treated, shrub_group, sep = "-"))
# 1. Assign shrub_treatment: either just the shrub_group or "buffer"
test <- test %>%
  mutate(shrub_treatment = ifelse(treated == "buffer", "buffer", paste(shrub_group) ),
         shrub_treatment = factor(shrub_treatment, levels = c("high", "mid", "low", "buffer")))
custom_colors <- c(
  "high"   = "#1a9641",  # green
  "mid"    = "orange",   # orange
  "low"    = "blue",     # blue
  "buffer" = "gray80"    # light gray
)

treatment_palette <- colorFactor(
  palette = custom_colors,
  domain = levels(test$shrub_treatment),  # ensures order is preserved
  ordered = TRUE
)

# Then use in leaflet
leaflet() %>%
  addProviderTiles("Esri.WorldImagery") %>%
  addPolygons(data = polygons_sf %>% st_transform(4326),
              fillColor = "white",
              fillOpacity = 0.2,
              color = "black",
              weight = 1,
              label = ~pasture) %>%
  addPolygons(data = test %>% st_transform(4326),
              fillColor = ~treatment_palette(shrub_treatment),
              color = "black",
              weight = 2,
              opacity = 1,
              fillOpacity = 0.7,
              label = ~paste("Shrub:", shrub_group, "<br>Status:", treated)) %>%
  addLegend("bottomright", pal = treatment_palette, values = test$shrub_treatment,
            title = "Shrub Cover of Treatment Cell", opacity = 1)

###########################

grid_sf <- st_sf(geometry = grid)
grid_sf$cell_id <- 1:nrow(grid_sf)
grids<- grid_sf %>%
  st_join(., reforma %>%
                    mutate(pasture = "reforma"), 
          join = st_within)  %>%
  st_join(., mes %>%
                    mutate(pasture = "mesq"), 
          join = st_within) %>%
  rename(pasture = pasture.x) %>%
  mutate(pasture = ifelse(!is.na(pasture.y), pasture.y, pasture)) %>%
  dplyr::select(-c(pasture.y)) %>%
  st_join(., , 
          join = st_within) %>%
  rename(pasture = pasture.x) %>%
  mutate(pasture = ifelse(!is.na(pasture.y), pasture.y, pasture)) %>%
  dplyr::select(-c(pasture.y)) %>%
  dplyr::select(c(cell_id, pasture, geometry)) %>%
  filter(!is.na(pasture))
mapview(grids, zcol = "pasture")  + mapview(reforma) + mapview(mes) + mapview(lmu %>% filter(Name %in% c("Chapote", "Corrales Prietas")) %>%
                                                                                st_union(.) %>% st_as_sf(.) %>% mutate(pasture = "mid"))
