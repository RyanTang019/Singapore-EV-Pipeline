# Data sources and attribution

The MIT License in [`LICENSE`](LICENSE) applies to this project's original code and
documentation. It does **not** replace the licences or terms that apply to third-party data.

The government datasets used by this project are made available under the
[Singapore Open Data Licence version 1.0](https://data.gov.sg/open-data-licence). That licence
requires acknowledgement of the source and a link to its latest version. The notices below cover
the source datasets represented in the repository and dashboard.

## Land Transport Authority (LTA) DataMall

The project uses these LTA DataMall datasets:

- **EV Charging Points Batch** (`EVCBatch`), first accessed 31 May 2026.
- **Traffic Speed Bands** (`TrafficSpeedBands`), first accessed 12 June 2026.
- **Carpark Availability** (`CarParkAvailabilityv2`), first accessed 12 June 2026.
- **Monthly Motor Vehicle Population Statistics by Type of Fuel Used (M09)**, retrieved
  23 July 2026. The committed controlled-source release covers January 2016 through May 2026.

Contains information from the datasets listed above, accessed from
[LTA DataMall](https://datamall.lta.gov.sg/content/datamall/en.html), which is made available under
the terms of the
[Singapore Open Data Licence version 1.0](https://datamall.lta.gov.sg/content/datamall/en/SingaporeOpenDataLicence.html).

The live feeds are accessed repeatedly by the production pipeline, so their contents and access
dates continue beyond the first-access dates stated above. The M09 source URL and retrieval
metadata are retained in
[`transform/seeds/lta_monthly_vehicle_population_releases.csv`](transform/seeds/lta_monthly_vehicle_population_releases.csv).

## Singapore Department of Statistics (SingStat)

The planning-area population seeds are derived from **Resident Population by Planning
Area/Subzone of Residence and Type of Dwelling (General Household Survey 2025)**, SingStat Table
Builder table `C020125`, retrieved 16 July 2026.

Contains information from that dataset, accessed from the
[SingStat Table Builder](https://tablebuilder.singstat.gov.sg/table/CT/C020125), which is made
available under the terms of the
[Singapore Open Data Licence version 1.0](https://data.gov.sg/open-data-licence) and is subject to
the [SingStat Terms of Use](https://www.singstat.gov.sg/terms-of-use).

The exact source identity, reference date, publication date, retrieval date, and checksum are
retained in
[`transform/seeds/planning_area_population_releases.csv`](transform/seeds/planning_area_population_releases.csv).

## Urban Redevelopment Authority (URA)

The planning-area boundary seed is derived from **Master Plan 2019 Planning Area Boundary (No
Sea)**, dataset `d_4765db0e87b9c86336792efe8a1f7a66`, accessed 10 July 2026 through data.gov.sg.

Contains information from that dataset, accessed from
[data.gov.sg](https://data.gov.sg/datasets/d_4765db0e87b9c86336792efe8a1f7a66/view), which is made
available under the terms of the
[Singapore Open Data Licence version 1.0](https://data.gov.sg/open-data-licence).

## No endorsement

This is an independent portfolio project. The Singapore Government, LTA, SingStat, URA, and any
other data provider have not endorsed this project or its analyses. Transformations,
classifications, calculations, and interpretations in this repository are the responsibility of
the project authors, not the source agencies.
