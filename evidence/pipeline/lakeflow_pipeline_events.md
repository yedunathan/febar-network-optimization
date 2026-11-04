# Lakeflow pipeline run: `lakeflow_pipeline`

_Task run `375841568862590` of job run `285440164007553` · result **SUCCESS** · 143s_

Pipeline id: `61cb3aba-c377-4392-af17-8adedeb1df75`

## Recent updates

| update_id | state | full_refresh | created |
|---|---|---|---|
| a4f427c4-00c9-4d12-b487-4aa0870f75b5 | COMPLETED | True | 2026-11-04 02:36:57Z |
| 181b03d7-bb66-4d03-b1f4-93e9b3fc3d50 | COMPLETED | True | 2026-11-04 01:35:13Z |

## Event log for update `a4f427c4-00c9-4d12-b487-4aa0870f75b5` (oldest first)

```text
2026-11-04T02:36:57.575Z  user_action      Principal 'build-user@[redacted]' started an update.
2026-11-04T02:36:57.589Z  create_update    Update a4f427 started by JOB_TASK.
2026-11-04T02:36:59.888Z  update_progress  Update a4f427 is WAITING_FOR_RESOURCES.
2026-11-04T02:37:05.163Z  runtime_details  Resolved runtime environment details for update a4f427.
2026-11-04T02:37:11.867Z  update_progress  Update a4f427 is INITIALIZING.
2026-11-04T02:38:14.942Z  update_progress  Update a4f427 is RESETTING.
2026-11-04T02:38:16.038Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.tms_freight has been successfully reset.
2026-11-04T02:38:16.263Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.erp_gl_line_items has been successfully reset.
2026-11-04T02:38:16.395Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.ref_shuttle_lanes has been successfully reset.
2026-11-04T02:38:16.547Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.erp_plant_xref has been successfully reset.
2026-11-04T02:38:16.732Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.tms_lineitem_detail has been successfully reset.
2026-11-04T02:38:17.046Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.tms_load has been successfully reset.
2026-11-04T02:38:17.098Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.ref_exchange_rates has been successfully reset.
2026-11-04T02:38:17.135Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.erp_plant_master has been successfully reset.
2026-11-04T02:38:17.345Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.tms_stop has been successfully reset.
2026-11-04T02:38:17.578Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.tms_lineitem has been successfully reset.
2026-11-04T02:38:17.646Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.mrp_supply_paths has been successfully reset.
2026-11-04T02:38:17.697Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.erp_inventory_monthly has been successfully reset.
2026-11-04T02:38:17.741Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.mrp_route_legs has been successfully reset.
2026-11-04T02:38:17.934Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.tms_rate has been successfully reset.
2026-11-04T02:38:18.075Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.erp_material_master has been successfully reset.
2026-11-04T02:38:18.204Z  dataset_life_cycle STREAMING_TABLE cpg_demos.netopt_bronze.ref_plant_coordinates has been successfully reset.
2026-11-04T02:38:18.436Z  update_progress  Update a4f427 is SETTING_UP_TABLES.
2026-11-04T02:38:35.563Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`ref_shuttle_lanes` defined as APPEND.
2026-11-04T02:38:35.601Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`erp_gl_line_items` defined as APPEND.
2026-11-04T02:38:35.607Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`erp_plant_xref` defined as APPEND.
2026-11-04T02:38:35.611Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`tms_lineitem_detail` defined as APPEND.
2026-11-04T02:38:35.614Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`tms_freight` defined as APPEND.
2026-11-04T02:38:35.618Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`erp_plant_master` defined as APPEND.
2026-11-04T02:38:35.622Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`ref_exchange_rates` defined as APPEND.
2026-11-04T02:38:35.626Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`tms_load` defined as APPEND.
2026-11-04T02:38:35.630Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`tms_stop` defined as APPEND.
2026-11-04T02:38:35.634Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`mrp_supply_paths` defined as APPEND.
2026-11-04T02:38:35.638Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`tms_lineitem` defined as APPEND.
2026-11-04T02:38:35.641Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`erp_inventory_monthly` defined as APPEND.
2026-11-04T02:38:35.645Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`mrp_route_legs` defined as APPEND.
2026-11-04T02:38:35.650Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`tms_rate` defined as APPEND.
2026-11-04T02:38:35.654Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`erp_material_master` defined as APPEND.
2026-11-04T02:38:35.658Z  flow_definition  Flow `cpg_demos`.`netopt_bronze`.`ref_plant_coordinates` defined as APPEND.
2026-11-04T02:38:35.661Z  flow_definition  Flow `cpg_demos`.`netopt_gold`.`inventory_monthly` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.665Z  flow_definition  Flow `cpg_demos`.`netopt_silver`.`enterprise_route_leg` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.668Z  flow_definition  Flow `cpg_demos`.`netopt_silver`.`enterprise_plant` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.677Z  flow_definition  Flow `cpg_demos`.`netopt_silver`.`freight_shipments` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.684Z  flow_definition  Flow `cpg_demos`.`netopt_silver`.`enterprise_material_master` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.693Z  flow_definition  Flow `cpg_demos`.`netopt_silver`.`enterprise_gl_line_item` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.704Z  flow_definition  Flow `cpg_demos`.`netopt_gold`.`lane_material_sot` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.711Z  flow_definition  Flow `cpg_demos`.`netopt_gold`.`material_period_status` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.714Z  flow_definition  Flow `cpg_demos`.`netopt_gold`.`lane_monthly` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.718Z  flow_definition  Flow `cpg_demos`.`netopt_gold`.`plant_stats` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.722Z  flow_definition  Flow `cpg_demos`.`netopt_gold`.`sales_monthly` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.726Z  flow_definition  Flow `cpg_demos`.`netopt_gold`.`oor_analysis` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.729Z  flow_definition  Flow `cpg_demos`.`netopt_silver`.`transport_lane_paths` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.751Z  dataset_definition Dataset `cpg_demos`.`netopt_silver`.`transport_lane_paths` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.770Z  dataset_definition Dataset `cpg_demos`.`netopt_gold`.`lane_material_sot` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.794Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`erp_inventory_monthly` defined as STREAMING_TABLE.
2026-11-04T02:38:35.804Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`erp_plant_master` defined as STREAMING_TABLE.
2026-11-04T02:38:35.813Z  dataset_definition Dataset `cpg_demos`.`netopt_gold`.`sales_monthly` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.822Z  dataset_definition Dataset `cpg_demos`.`netopt_silver`.`freight_shipments` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.834Z  dataset_definition Dataset `cpg_demos`.`netopt_silver`.`enterprise_plant` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.844Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`tms_lineitem_detail` defined as STREAMING_TABLE.
2026-11-04T02:38:35.853Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`erp_plant_xref` defined as STREAMING_TABLE.
2026-11-04T02:38:35.862Z  dataset_definition Dataset `cpg_demos`.`netopt_silver`.`enterprise_material_master` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.872Z  dataset_definition Dataset `cpg_demos`.`netopt_silver`.`enterprise_route_leg` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.881Z  dataset_definition Dataset `cpg_demos`.`netopt_gold`.`inventory_monthly` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.891Z  dataset_definition Dataset `cpg_demos`.`netopt_silver`.`enterprise_gl_line_item` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.901Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`ref_shuttle_lanes` defined as STREAMING_TABLE.
2026-11-04T02:38:35.911Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`tms_freight` defined as STREAMING_TABLE.
2026-11-04T02:38:35.920Z  dataset_definition Dataset `cpg_demos`.`netopt_gold`.`oor_analysis` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.930Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`erp_gl_line_items` defined as STREAMING_TABLE.
2026-11-04T02:38:35.940Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`tms_lineitem` defined as STREAMING_TABLE.
2026-11-04T02:38:35.949Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`tms_stop` defined as STREAMING_TABLE.
2026-11-04T02:38:35.959Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`ref_plant_coordinates` defined as STREAMING_TABLE.
2026-11-04T02:38:35.968Z  dataset_definition Dataset `cpg_demos`.`netopt_gold`.`lane_monthly` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:35.978Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`mrp_supply_paths` defined as STREAMING_TABLE.
2026-11-04T02:38:35.987Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`erp_material_master` defined as STREAMING_TABLE.
2026-11-04T02:38:35.997Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`mrp_route_legs` defined as STREAMING_TABLE.
2026-11-04T02:38:36.006Z  dataset_definition Dataset `cpg_demos`.`netopt_gold`.`material_period_status` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:36.015Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`tms_load` defined as STREAMING_TABLE.
2026-11-04T02:38:36.025Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`ref_exchange_rates` defined as STREAMING_TABLE.
2026-11-04T02:38:36.034Z  dataset_definition Dataset `cpg_demos`.`netopt_gold`.`plant_stats` defined as MATERIALIZED_VIEW.
2026-11-04T02:38:36.043Z  dataset_definition Dataset `cpg_demos`.`netopt_bronze`.`tms_rate` defined as STREAMING_TABLE.
2026-11-04T02:38:36.100Z  graph_created    Dataflow graph successfully loaded.
2026-11-04T02:38:36.106Z  update_progress  Update a4f427 is RUNNING.
2026-11-04T02:38:36.118Z  flow_progress    Flow 'cpg_demos.netopt_bronze.mrp_route_legs' is QUEUED.
2026-11-04T02:38:36.123Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_gl_line_item' is QUEUED.
2026-11-04T02:38:36.125Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_lineitem' is QUEUED.
2026-11-04T02:38:36.127Z  flow_progress    Flow 'cpg_demos.netopt_gold.lane_monthly' is QUEUED.
2026-11-04T02:38:36.129Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_stop' is QUEUED.
2026-11-04T02:38:36.130Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_material_master' is QUEUED.
2026-11-04T02:38:36.132Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_exchange_rates' is QUEUED.
2026-11-04T02:38:36.133Z  flow_progress    Flow 'cpg_demos.netopt_bronze.mrp_supply_paths' is QUEUED.
2026-11-04T02:38:36.135Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_plant' is QUEUED.
2026-11-04T02:38:36.136Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_inventory_monthly' is QUEUED.
2026-11-04T02:38:36.137Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_gl_line_items' is QUEUED.
2026-11-04T02:38:36.139Z  flow_progress    Flow 'cpg_demos.netopt_silver.freight_shipments' is QUEUED.
2026-11-04T02:38:36.141Z  flow_progress    Flow 'cpg_demos.netopt_gold.plant_stats' is QUEUED.
2026-11-04T02:38:36.143Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_plant_master' is QUEUED.
2026-11-04T02:38:36.145Z  flow_progress    Flow 'cpg_demos.netopt_gold.oor_analysis' is QUEUED.
2026-11-04T02:38:36.147Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_plant_xref' is QUEUED.
2026-11-04T02:38:36.148Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_shuttle_lanes' is QUEUED.
2026-11-04T02:38:36.149Z  flow_progress    Flow 'cpg_demos.netopt_gold.sales_monthly' is QUEUED.
2026-11-04T02:38:36.151Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_lineitem_detail' is QUEUED.
2026-11-04T02:38:36.152Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_rate' is QUEUED.
2026-11-04T02:38:36.153Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_load' is QUEUED.
2026-11-04T02:38:36.155Z  flow_progress    Flow 'cpg_demos.netopt_gold.inventory_monthly' is QUEUED.
2026-11-04T02:38:36.156Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_freight' is QUEUED.
2026-11-04T02:38:36.157Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_material_master' is QUEUED.
2026-11-04T02:38:36.159Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_route_leg' is QUEUED.
2026-11-04T02:38:36.160Z  flow_progress    Flow 'cpg_demos.netopt_gold.material_period_status' is QUEUED.
2026-11-04T02:38:36.161Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_plant_coordinates' is QUEUED.
2026-11-04T02:38:36.163Z  flow_progress    Flow 'cpg_demos.netopt_silver.transport_lane_paths' is QUEUED.
2026-11-04T02:38:36.164Z  flow_progress    Flow 'cpg_demos.netopt_gold.lane_material_sot' is QUEUED.
2026-11-04T02:38:36.381Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_exchange_rates' is STARTING.
2026-11-04T02:38:38.127Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_exchange_rates' is RUNNING.
2026-11-04T02:38:38.565Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_gl_line_items' is STARTING.
2026-11-04T02:38:39.227Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_gl_line_items' is RUNNING.
2026-11-04T02:38:39.443Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_stop' is STARTING.
2026-11-04T02:38:40.196Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_stop' is RUNNING.
2026-11-04T02:38:40.430Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_inventory_monthly' is STARTING.
2026-11-04T02:38:41.050Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_inventory_monthly' is RUNNING.
2026-11-04T02:38:41.246Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_lineitem_detail' is STARTING.
2026-11-04T02:38:41.918Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_lineitem_detail' is RUNNING.
2026-11-04T02:38:42.108Z  flow_progress    Flow 'cpg_demos.netopt_bronze.mrp_route_legs' is STARTING.
2026-11-04T02:38:42.830Z  flow_progress    Flow 'cpg_demos.netopt_bronze.mrp_route_legs' is RUNNING.
2026-11-04T02:38:43.015Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_freight' is STARTING.
2026-11-04T02:38:43.789Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_freight' is RUNNING.
2026-11-04T02:38:43.968Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_material_master' is STARTING.
2026-11-04T02:38:44.817Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_material_master' is RUNNING.
2026-11-04T02:38:45.001Z  flow_progress    Flow 'cpg_demos.netopt_bronze.mrp_supply_paths' is STARTING.
2026-11-04T02:38:45.727Z  flow_progress    Flow 'cpg_demos.netopt_bronze.mrp_supply_paths' is RUNNING.
2026-11-04T02:38:45.969Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_plant_xref' is STARTING.
2026-11-04T02:38:46.424Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.ref_exchange_rates'.
2026-11-04T02:38:46.544Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.erp_gl_line_items'.
2026-11-04T02:38:46.552Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.tms_stop'.
2026-11-04T02:38:46.560Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.erp_inventory_monthly'.
2026-11-04T02:38:46.568Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.tms_lineitem_detail'.
2026-11-04T02:38:46.590Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_lineitem_detail' has COMPLETED.
2026-11-04T02:38:46.598Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_exchange_rates' has COMPLETED.
2026-11-04T02:38:46.603Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_gl_line_items' has COMPLETED.
2026-11-04T02:38:46.608Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_stop' has COMPLETED.
2026-11-04T02:38:46.615Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_inventory_monthly' has COMPLETED.
2026-11-04T02:38:46.825Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_plant_xref' is RUNNING.
2026-11-04T02:38:47.038Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_plant_coordinates' is STARTING.
2026-11-04T02:38:47.224Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.mrp_route_legs'.
2026-11-04T02:38:47.309Z  flow_progress    Flow 'cpg_demos.netopt_bronze.mrp_route_legs' has COMPLETED.
2026-11-04T02:38:47.696Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_plant_coordinates' is RUNNING.
2026-11-04T02:38:47.816Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.tms_freight'.
2026-11-04T02:38:47.881Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_freight' has COMPLETED.
2026-11-04T02:38:47.887Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_plant_master' is STARTING.
2026-11-04T02:38:48.682Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_plant_master' is RUNNING.
2026-11-04T02:38:48.905Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_shuttle_lanes' is STARTING.
2026-11-04T02:38:49.086Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.erp_material_master'.
2026-11-04T02:38:49.165Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_material_master' has COMPLETED.
2026-11-04T02:38:49.656Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_shuttle_lanes' is RUNNING.
2026-11-04T02:38:49.823Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.mrp_supply_paths'.
2026-11-04T02:38:49.838Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_lineitem' is STARTING.
2026-11-04T02:38:49.901Z  flow_progress    Flow 'cpg_demos.netopt_bronze.mrp_supply_paths' has COMPLETED.
2026-11-04T02:38:50.501Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_lineitem' is RUNNING.
2026-11-04T02:38:50.721Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_load' is STARTING.
2026-11-04T02:38:50.897Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.erp_plant_xref'.
2026-11-04T02:38:50.970Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_plant_xref' has COMPLETED.
2026-11-04T02:38:51.411Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_load' is RUNNING.
2026-11-04T02:38:51.621Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.ref_plant_coordinates'.
2026-11-04T02:38:51.647Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_rate' is STARTING.
2026-11-04T02:38:51.730Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_plant_coordinates' has COMPLETED.
2026-11-04T02:38:52.281Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_rate' is RUNNING.
2026-11-04T02:38:52.816Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.erp_plant_master'.
2026-11-04T02:38:52.896Z  flow_progress    Flow 'cpg_demos.netopt_bronze.erp_plant_master' has COMPLETED.
2026-11-04T02:38:53.452Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.ref_shuttle_lanes'.
2026-11-04T02:38:53.524Z  flow_progress    Flow 'cpg_demos.netopt_bronze.ref_shuttle_lanes' has COMPLETED.
2026-11-04T02:38:54.510Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.tms_lineitem'.
2026-11-04T02:38:54.517Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_material_master' is PLANNING.
2026-11-04T02:38:54.519Z  flow_progress    Flow 'cpg_demos.netopt_silver.transport_lane_paths' is PLANNING.
2026-11-04T02:38:54.521Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_route_leg' is PLANNING.
2026-11-04T02:38:54.523Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_plant' is PLANNING.
2026-11-04T02:38:54.535Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_gl_line_item' is PLANNING.
2026-11-04T02:38:54.537Z  flow_progress    Flow 'cpg_demos.netopt_gold.inventory_monthly' is PLANNING.
2026-11-04T02:38:54.593Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_lineitem' has COMPLETED.
2026-11-04T02:38:55.110Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.tms_load'.
2026-11-04T02:38:55.177Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_load' has COMPLETED.
2026-11-04T02:38:55.476Z  planning_information Flow 'cpg_demos.netopt_silver.enterprise_plant' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:38:55.515Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_plant' is STARTING.
2026-11-04T02:38:55.637Z  planning_information Flow 'cpg_demos.netopt_silver.transport_lane_paths' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:38:55.648Z  flow_progress    Flow 'cpg_demos.netopt_silver.transport_lane_paths' is STARTING.
2026-11-04T02:38:55.666Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_plant' is RUNNING.
2026-11-04T02:38:55.688Z  planning_information Flow 'cpg_demos.netopt_silver.enterprise_route_leg' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:38:55.696Z  planning_information Flow 'cpg_demos.netopt_silver.enterprise_gl_line_item' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:38:55.699Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_gl_line_item' is STARTING.
2026-11-04T02:38:55.708Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_route_leg' is STARTING.
2026-11-04T02:38:55.730Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_gl_line_item' is RUNNING.
2026-11-04T02:38:55.739Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_route_leg' is RUNNING.
2026-11-04T02:38:55.741Z  planning_information Flow 'cpg_demos.netopt_gold.inventory_monthly' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:38:55.744Z  flow_progress    Flow 'cpg_demos.netopt_gold.inventory_monthly' is STARTING.
2026-11-04T02:38:55.749Z  planning_information Flow 'cpg_demos.netopt_silver.enterprise_material_master' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:38:55.762Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_material_master' is STARTING.
2026-11-04T02:38:55.769Z  flow_progress    Flow 'cpg_demos.netopt_gold.inventory_monthly' is RUNNING.
2026-11-04T02:38:55.813Z  flow_progress    Flow 'cpg_demos.netopt_silver.transport_lane_paths' is RUNNING.
2026-11-04T02:38:55.826Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_material_master' is RUNNING.
2026-11-04T02:38:56.811Z  flow_progress    Completed a streaming update of 'cpg_demos.netopt_bronze.tms_rate'.
2026-11-04T02:38:56.887Z  flow_progress    Flow 'cpg_demos.netopt_bronze.tms_rate' has COMPLETED.
2026-11-04T02:38:57.834Z  flow_progress    Flow 'cpg_demos.netopt_silver.freight_shipments' is PLANNING.
2026-11-04T02:38:59.528Z  planning_information Flow 'cpg_demos.netopt_silver.freight_shipments' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:38:59.535Z  flow_progress    Flow 'cpg_demos.netopt_silver.freight_shipments' is STARTING.
2026-11-04T02:38:59.752Z  flow_progress    Flow 'cpg_demos.netopt_silver.freight_shipments' is RUNNING.
2026-11-04T02:39:01.559Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_gl_line_item' has COMPLETED.
2026-11-04T02:39:01.623Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_material_master' has COMPLETED.
2026-11-04T02:39:01.708Z  flow_progress    Flow 'cpg_demos.netopt_gold.sales_monthly' is PLANNING.
2026-11-04T02:39:01.712Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_route_leg' has COMPLETED.
2026-11-04T02:39:01.775Z  flow_progress    Flow 'cpg_demos.netopt_silver.enterprise_plant' has COMPLETED.
2026-11-04T02:39:01.805Z  flow_progress    Flow 'cpg_demos.netopt_silver.transport_lane_paths' has COMPLETED.
2026-11-04T02:39:01.898Z  flow_progress    Flow 'cpg_demos.netopt_gold.inventory_monthly' has COMPLETED.
2026-11-04T02:39:01.921Z  planning_information Flow 'cpg_demos.netopt_gold.sales_monthly' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:39:01.924Z  flow_progress    Flow 'cpg_demos.netopt_gold.sales_monthly' is STARTING.
2026-11-04T02:39:01.951Z  flow_progress    Flow 'cpg_demos.netopt_gold.sales_monthly' is RUNNING.
2026-11-04T02:39:05.109Z  flow_progress    Flow 'cpg_demos.netopt_silver.freight_shipments' has COMPLETED.
2026-11-04T02:39:05.156Z  flow_progress    Flow 'cpg_demos.netopt_gold.sales_monthly' has COMPLETED.
2026-11-04T02:39:05.162Z  flow_progress    Flow 'cpg_demos.netopt_gold.lane_material_sot' is PLANNING.
2026-11-04T02:39:06.345Z  planning_information Flow 'cpg_demos.netopt_gold.lane_material_sot' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:39:06.349Z  flow_progress    Flow 'cpg_demos.netopt_gold.lane_material_sot' is STARTING.
2026-11-04T02:39:06.470Z  flow_progress    Flow 'cpg_demos.netopt_gold.lane_material_sot' is RUNNING.
2026-11-04T02:39:10.513Z  flow_progress    Flow 'cpg_demos.netopt_gold.lane_material_sot' has COMPLETED.
2026-11-04T02:39:10.521Z  flow_progress    Flow 'cpg_demos.netopt_gold.oor_analysis' is PLANNING.
2026-11-04T02:39:10.523Z  flow_progress    Flow 'cpg_demos.netopt_gold.lane_monthly' is PLANNING.
2026-11-04T02:39:10.525Z  flow_progress    Flow 'cpg_demos.netopt_gold.material_period_status' is PLANNING.
2026-11-04T02:39:10.526Z  flow_progress    Flow 'cpg_demos.netopt_gold.plant_stats' is PLANNING.
2026-11-04T02:39:10.746Z  planning_information Flow 'cpg_demos.netopt_gold.lane_monthly' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:39:10.749Z  flow_progress    Flow 'cpg_demos.netopt_gold.lane_monthly' is STARTING.
2026-11-04T02:39:10.823Z  flow_progress    Flow 'cpg_demos.netopt_gold.lane_monthly' is RUNNING.
2026-11-04T02:39:10.896Z  planning_information Flow 'cpg_demos.netopt_gold.plant_stats' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:39:10.900Z  flow_progress    Flow 'cpg_demos.netopt_gold.plant_stats' is STARTING.
2026-11-04T02:39:10.904Z  planning_information Flow 'cpg_demos.netopt_gold.material_period_status' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:39:10.908Z  flow_progress    Flow 'cpg_demos.netopt_gold.material_period_status' is STARTING.
2026-11-04T02:39:10.962Z  flow_progress    Flow 'cpg_demos.netopt_gold.plant_stats' is RUNNING.
2026-11-04T02:39:10.979Z  flow_progress    Flow 'cpg_demos.netopt_gold.material_period_status' is RUNNING.
2026-11-04T02:39:11.132Z  planning_information Flow 'cpg_demos.netopt_gold.oor_analysis' has been planned to be executed as COMPLETE_RECOMPUTE.
2026-11-04T02:39:11.136Z  flow_progress    Flow 'cpg_demos.netopt_gold.oor_analysis' is STARTING.
2026-11-04T02:39:11.312Z  flow_progress    Flow 'cpg_demos.netopt_gold.oor_analysis' is RUNNING.
2026-11-04T02:39:15.142Z  flow_progress    Flow 'cpg_demos.netopt_gold.material_period_status' has COMPLETED.
2026-11-04T02:39:15.165Z  flow_progress    Flow 'cpg_demos.netopt_gold.lane_monthly' has COMPLETED.
2026-11-04T02:39:15.226Z  flow_progress    Flow 'cpg_demos.netopt_gold.plant_stats' has COMPLETED.
2026-11-04T02:39:16.082Z  flow_progress    Flow 'cpg_demos.netopt_gold.oor_analysis' has COMPLETED.
2026-11-04T02:39:16.128Z  update_progress  Update a4f427 is COMPLETED.
```
