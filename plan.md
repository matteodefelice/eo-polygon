# OBJECTIVE
I want to explore the possibility of using OpenEO and Google Earth Engine to generate data cubes for a single polygon (farm) to analise the impact between biodiversity, climate and yields. This is a preparatory work to create a scalable system to analyse a large portfolio of rural clients. 

# PLAN
Given a polygon coming from a WKT representation, return a set of xarray data arrays with dimension latitude, longitude and time for the following variables:
- NDVI
- Cloud mask or cloud cover (something needed to mask)
- Land/ground temperature

When the variables have the same dimensions they can be merged into the same xarray dataset. 

Create a set of functions that can be reused in Python notebooks (no jupyter) using both OpenEO and Google Earth Engine. 
All the relevant configuration variables should be kept in a separate YAML file 
# REQUIREMENTS
- Write simple and minimal code, scientific style. 
- Check the documentation
- Memorise authentication, saving tokens/codes/usernames/accounts in the YAML file