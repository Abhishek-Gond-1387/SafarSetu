import time
from app.services.data_source_service import TransitContext

TransitContext.initialize()
dataset = TransitContext.dataset
print("Total trips:", len(dataset.trips))
dmrc_trips = [t for t in dataset.trips.values() if t.source_id == 'dmrc' or 'metro_' in t.trip_id]
print("DMRC trips:", len(dmrc_trips))

# Check stop_times for Rajiv Chowk (metro_50) and Hauz Khas (metro_59)
st_50 = dataset.stop_times.get('metro_50', [])
st_59 = dataset.stop_times.get('metro_59', [])
print("Stop times for Rajiv Chowk (metro_50):", len(st_50))
print("Stop times for Hauz Khas (metro_59):", len(st_59))

if st_50:
    print("Sample Rajiv Chowk trip_id:", st_50[0].trip_id, "dep:", st_50[0].departure_time)

# Check graph edges from metro_50
edges_50 = TransitContext.graph.get_outgoing_edges('metro_50')
print("Outgoing edges from metro_50:", len(edges_50))
for e in edges_50[:10]:
    print("  ->", e.to_stop_id, e.mode, e.route_id)

