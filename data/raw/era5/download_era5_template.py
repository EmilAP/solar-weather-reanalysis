import cdsapi

c = cdsapi.Client()
c.retrieve(
    'reanalysis-era5-single-levels',
    {
        # Copy fields from era5_request_template.json and adjust scope before running
    },
    'era5_output.nc'
)
