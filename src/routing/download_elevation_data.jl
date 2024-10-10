# Download the elevation data

using Downloads, Logging, ProgressMeter

function download_with_progress(url, outfile)
    progress = nothing

    Downloads.download(url, outfile, progress=(total, now) -> begin
        if isnothing(progress) && now > 0
            if total == 0
                progress = ProgressUnknown()
            else
                progress = Progress(total)
            end
        end

        if !isnothing(progress)
            update!(progress, now)
        end

    end)

    if !isnothing(progress)
        finish!(progress)
    end
end

function main()
    outdir = ARGS[1]

    if !isdir(outdir)
        error("outdir is not a path")
    end

    # off-by-one - because longitudes are negative, n43w094 actually contains -94 to -93.
    for lat in 43:46, lon in 93:95
        tile = "n$(lat)w0$(lon)"
        filename = "USGS_13_$(tile).tif"
        outfile = joinpath(outdir, filename)

        if isfile(outfile)
            @info "Skipping file $filename, already exists in output directory"
        else
            @info "Downloading file $filename"
            download_with_progress("https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/current/$(tile)/$(filename)", outfile)
        end
    end
end

main()