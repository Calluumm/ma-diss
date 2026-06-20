library(chirps)
library(dotenv)
library(sf)
library(terra)

load_dot_env("C:\\Users\\Student\\Desktop\\Masters\\Dissertation\\03_Methods\\01_Mapping\\.env")

envnum <- function(primary, fallback = "") {
  raw <- Sys.getenv(primary, unset = "")
  if (identical(raw, "") && !identical(fallback, "")) {
    raw <- Sys.getenv(fallback, unset = "")
  }
  if (identical(raw, "")) {
    return(NA_real_)
  }
  as.numeric(raw)
}

envdate <- function(primary, fallback = "") {
  raw <- Sys.getenv(primary, unset = "")
  if (identical(raw, "") && !identical(fallback, "")) {
    raw <- Sys.getenv(fallback, unset = "")
  }
  if (identical(raw, "")) {
    return(NA_character_)
  }

  parsed <- as.Date(raw)
  if (is.na(parsed)) {
    stop(sprintf("Invalid date for %s: '%s'. Use YYYY-MM-DD.", primary, raw))
  }
  format(parsed, "%Y-%m-%d")
}

xmin <- envnum("BBOX_XMIN", "BBOX_WEST")
ymin <- envnum("BBOX_YMIN", "BBOX_SOUTH")
xmax <- envnum("BBOX_XMAX", "BBOX_EAST")
ymax <- envnum("BBOX_YMAX", "BBOX_NORTH")

bbox_vals <- c(xmin, ymin, xmax, ymax)
if (any(!is.finite(bbox_vals))) {
  stop("Invalid bbox er1")
}
if (!(xmin < xmax && ymin < ymax)) {
  stop("invalid bbox er2")
}

cat(sprintf("  X: %.3f to %.3f°E\n  Y: %.3f to %.3f°N\n", xmin, xmax, ymin, ymax))

centre_lon <- (xmin + xmax) / 2
centre_lat <- (ymin + ymax) / 2
if (!is.finite(centre_lon) || !is.finite(centre_lat)) {
  stop("catchment centre invalid er1")
}
if (centre_lon < -180 || centre_lon > 180 || centre_lat < -90 || centre_lat > 90) {
  stop("catchment centre invalid er2")
}

catchcentre <- data.frame(
  lon = centre_lon,
  lat = centre_lat
)

#date range
startd <- envdate("C_START")
endd <- envdate("C_END")

chirps_server <- Sys.getenv("CHIRPS_SERVER", unset = "CHC")
if (!(chirps_server %in% c("CHC", "ClimateSERV"))) {
  stop("Invalid CHIRPS_SERVER. Use 'CHC' or 'ClimateSERV'.")
}

cat(sprintf("\nDate range: %s to %s\n", startd, endd))
cat(sprintf("CHIRPS server: %s\n", chirps_server))

cat("chirps api lookup\n")
download_chirps <- function(server_name) {
  tryCatch(
    {
      get_chirps(
        object = catchcentre,
        dates = c(startd, endd),
        server = server_name
      )
    },
    error = function(e) {
      cat(sprintf("Error with server, server%s: %s\n", server_name, conditionMessage(e)))
      return(NULL)
    }
  )
}

rawchirps <- download_chirps(chirps_server)

if (is.null(rawchirps) && chirps_server == "CHC") {
  cat("retryingV\n")
  rawchirps <- download_chirps("ClimateSERV")
}

if (!is.null(rawchirps)) {
  cat("download worked\n")
  print(head(rawchirps))
  
  output_dir <- "02_Data/01_Raw/CHIRPS"
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }
  
  output_file <- file.path(output_dir, "palanan_chirps_2016-2026.csv")
  write.csv(rawchirps, output_file, row.names = FALSE)
  cat(sprintf("saved to: %s\n", output_file))
  
} else {
  cat("Failed\n")
}
