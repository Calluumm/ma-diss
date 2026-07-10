args <- commandArgs(trailingOnly = TRUE)
getargvalue <- function(flag, defaultvalue) {
  idx <- which(args == flag)
  if (length(idx) == 0 || idx[length(idx)] == length(args)) {
    return(defaultvalue)
  }
  args[idx[length(idx)] + 1]
}

scriptpath <- NULL
cmdall <- commandArgs(trailingOnly = FALSE)
filearg <- grep("^--file=", cmdall, value = TRUE)
if (length(filearg) > 0) {
  scriptpath <- normalizePath(sub("^--file=", "", filearg[1]), winslash = "/", mustWork = FALSE)
}

if (is.null(scriptpath) || !nzchar(scriptpath)) {
  reporoot <- getwd()
} else {
  reporoot <- normalizePath(file.path(dirname(scriptpath), "..", ".."), winslash = "/", mustWork = FALSE)
}

inputcsv <- getargvalue("--input", file.path(reporoot, "04_Analysis", "channel_rainfall_summary.csv"))
outdir <- getargvalue("--outdir", file.path(reporoot, "05_Figures", "channel_rainfall"))

dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

df <- read.csv(inputcsv, stringsAsFactors = FALSE)

df$post_date <- as.Date(df$post_date)
df$pre_date <- as.Date(df$pre_date)
df <- df[order(df$post_date), ]
df$cumulative_net_change_ha <- cumsum(df$net_change_area_ha)

hascontextcols <- all(c("context_mode", "context_period_pre", "context_period_post", "context_mm_pre", "context_mm_post") %in% names(df))

themeplot <- function() {
  par(
    bty = "l",
    col.axis = "#1E2A38",
    col.lab = "#1E2A38",
    col.main = "#102030",
    cex.axis = 0.9,
    cex.lab = 1,
    cex.main = 1.1,
    las = 1
  )
}

# 1) Change components over time
png(file.path(outdir, "channel_change_components_overtime.png"), width = 1600, height = 900, res = 160)
themeplot()
matplot(
  x = df$post_date,
  y = cbind(df$gain_area_ha, df$loss_area_ha, df$change_area_ha),
  type = "o",
  pch = c(16, 17, 15),
  lty = 1,
  lwd = 2,
  col = c("#1b9e77", "#d95f02", "#7570b3"),
  xlab = "Post date",
  ylab = "Area (ha)",
  main = "Channel Change Components Through Time"
)
legend(
  "topright",
  legend = c("Gain area", "Loss area", "Total change area"),
  col = c("#1b9e77", "#d95f02", "#7570b3"),
  lty = 1,
  pch = c(16, 17, 15),
  lwd = 2,
  bg = "white"
)
dev.off()

# 2) Net and cumulative net change over time
png(file.path(outdir, "channel_net_change_overtime.png"), width = 1600, height = 900, res = 160)
themeplot()
netplotrange <- range(c(df$net_change_area_ha, df$cumulative_net_change_ha, 0), na.rm = TRUE)
plot(
  df$post_date,
  df$net_change_area_ha,
  type = "o",
  pch = 16,
  lwd = 2,
  col = "#2c7fb8",
  xlab = "Post date",
  ylab = "Net change area (ha)",
  main = "Net Channel Change Through Time",
  ylim = netplotrange
)
abline(h = 0, lty = 2, col = "#7f8c8d")
lines(df$post_date, df$cumulative_net_change_ha, type = "o", pch = 15, lwd = 2, col = "#e31a1c")
legend(
  "topright",
  legend = c("Net change per interval", "Cumulative net change"),
  col = c("#2c7fb8", "#e31a1c"),
  lty = 1,
  pch = c(16, 15),
  lwd = 2,
  bg = "white"
)
dev.off()

# 3) Context rainfall through time, if available
if (hascontextcols) {
  png(file.path(outdir, "context_rainfall_through_time.png"), width = 1600, height = 900, res = 160)
  themeplot()
  contextlabel <- unique(na.omit(df$context_mode))
  if (length(contextlabel) == 0) {
    contextlabel <- "context"
  } else {
    contextlabel <- contextlabel[1]
  }

  plot(
    df$post_date,
    df$context_mm_post,
    type = "o",
    pch = 16,
    lwd = 2,
    col = "#1f78b4",
    xlab = "Post date",
    ylab = "Rainfall context (mm)",
    main = sprintf("Rainfall Context Through Time (%s)", contextlabel)
  )
  lines(df$post_date, df$context_mm_pre, type = "o", pch = 15, lwd = 2, col = "#33a02c")
  legend(
    "topright",
    legend = c("Post-period context", "Pre-period context"),
    col = c("#1f78b4", "#33a02c"),
    lty = 1,
    pch = c(16, 15),
    lwd = 2,
    bg = "white"
  )
  dev.off()
}

# 4) Rainfall and change stacked panels
png(file.path(outdir, "rainfall_and_channel_change_panels.png"), width = 1600, height = 1200, res = 160)
par(mfrow = c(2, 1), mar = c(4, 5, 3, 2), oma = c(0, 0, 1, 0))
themeplot()
plot(
  df$post_date,
  df$rain_mm_interval,
  type = "o",
  pch = 16,
  lwd = 2,
  col = "#1f78b4",
  xlab = "Post date",
  ylab = "Rainfall over interval (mm)",
  main = "Interval Rainfall Through Time"
)
plot(
  df$post_date,
  df$change_area_ha,
  type = "o",
  pch = 16,
  lwd = 2,
  col = "#33a02c",
  xlab = "Post date",
  ylab = "Total channel change area (ha)",
  main = "Channel Change Through Time"
)
mtext("Rainfall and Channel Change Over Time", outer = TRUE, cex = 1.2, col = "#102030")
dev.off()

# 5) Rainfall vs change scatter
png(file.path(outdir, "rainfall_vs_change_scatter.png"), width = 1400, height = 900, res = 160)
themeplot()
plot(
  df$rain_mm_interval,
  df$change_area_ha,
  pch = 16,
  col = "#6a3d9a",
  xlab = "Interval rainfall (mm)",
  ylab = "Total channel change area (ha)",
  main = "Rainfall vs Channel Change"
)
if (nrow(df) >= 2) {
  model <- lm(change_area_ha ~ rain_mm_interval, data = df)
  abline(model, col = "#e31a1c", lwd = 2)
  legend("topleft", legend = sprintf("R^2 = %.3f", summary(model)$r.squared), bty = "n")
}
dev.off()
