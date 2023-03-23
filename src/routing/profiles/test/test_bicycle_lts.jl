include("util.jl")

using Geodesy, Test

function main(osrm)
    @testset "Beaudry Meadows Park" begin
        # This is a route near Beaudry Meadows Park in Albertville
        # A trip along 77th St from Lamont Ave to Large Ave incorrectly deviated north to 70th St via the
        # Lancaster Ave sidewalk, to avoid crossing a highway=service link with a high LTS.
        # Service roads should definitely not discourage crossing.
        @test route_nodes(osrm, LatLon(45.2622784, -93.6572516), LatLon(45.2634825, -93.6529270), [
            1996506443,
            5402303219,
            1813232814,
            5396345618,
            5396345617,
            1996506391,
            5396345616,
            5396345615,
            5396345614,
            1813232822,
            5396345613,
            5396345612,
            5396345611,
            5402303242,
            1813233258,
            5396345610,
            5402303245,
            1813232816,
            5396345609,
            5402303273,
            1813232815,
            5396345608
        ])
    end
end

run_tests(main)