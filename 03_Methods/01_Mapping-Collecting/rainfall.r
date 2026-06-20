library(dotenv)

load_dot_env("C:\\Users\\Student\\Desktop\\Masters\\Dissertation\\03_Methods\\01_Mapping\\.env")
setwd("C:\\Users\\Student\\Desktop\\Masters\\Dissertation\\02_Data\\01_Raw\\CHIRPS")
rainfall_data <- "palanan_chirps_2016-2026.csv"
#id, lon, lat, date, chirps

fileTot <- Sys.getenv("YEARLY_TOTAL")
fileMAM   <- Sys.getenv("YEARLY_MAM")

df <- read.csv(rainfall_data)
df$date <- as.Date(df$date)
df$year  <- as.integer(format(df$date, "%Y"))
df$month <- as.integer(format(df$date, "%m"))

yearlyTot <- aggregate(chirps ~ year, data = df, FUN = sum, na.rm = TRUE)
names(yearlyTot)[2] <- "total_mm"
write.csv(yearlyTot, fileTot, row.names = FALSE)

dfMAM <- df[df$month %in% c(3, 4, 5), ]
yearlyMAM <- aggregate(chirps ~ year, data = dfMAM, FUN = sum, na.rm = TRUE)
names(yearlyMAM)[2] <- "total_mm_MAM"
write.csv(yearlyMAM, fileMAM, row.names = FALSE)

yearlyTot <- read.csv(fileTot)
yearlyMAM   <- read.csv(fileMAM)

png("plot_yearly_total_rainfall.png", width = 900, height = 500)
plot(
  yearlyTot$year, yearlyTot$total_mm,
  type = "o", pch = 16, col = "steelblue",
  xlab = "Year", ylab = "Total Rainfall (mm)",
  main = "Yearly Total Rainfall – Palanan Catchment",
  xaxt = "n"
)
axis(1, at = yearlyTot$year, labels = yearlyTot$year)
grid()
dev.off()

png("plot_yearly_MAM_rainfall.png", width = 900, height = 500)
plot(
  yearlyMAM$year, yearlyMAM$total_mm_MAM,
  type = "o", pch = 16, col = "darkorange",
  xlab = "Year", ylab = "MAM Rainfall (mm)",
  main = "Yearly Mar–Apr–May Rainfall – Palanan Catchment",
  xaxt = "n"
)
axis(1, at = yearlyMAM$year, labels = yearlyMAM$year)
grid()
dev.off()
