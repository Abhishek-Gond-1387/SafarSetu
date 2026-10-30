"""Unit tests for public transport routing engine and ranking algorithms."""
from datetime import date
import pytest

from app.models.journey import LegMode, RouteRankCriterion
from app.models.transit import (
    CalendarDate,
    CalendarService,
    ExceptionType,
    GTFSDataset,
    Route,
    RouteType,
    Stop,
    StopTime,
    Trip,
)
from app.services.graph_builder import GraphBuilder
from app.services.route_ranker import RouteRanker
from app.services.routing_engine import RoutingEngine


@pytest.fixture
def mini_transit_network():
    """Build a minimal isolated graph:
    STOP_A -> STOP_B -> STOP_C on Route 1 (Trip 1, 08:00 to 08:30)
    STOP_C -> STOP_D on Route 2 (Trip 2, 08:35 to 09:00)
    STOP_ISOLATED (no connections)
    """
    stops = {
        "A": Stop("A", "Stop Alpha", 28.6100, 77.2100),
        "B": Stop("B", "Stop Beta", 28.6200, 77.2200),
        "C": Stop("C", "Stop Gamma", 28.6300, 77.2300),
        "D": Stop("D", "Stop Delta", 28.6400, 77.2400),
        "ISO": Stop("ISO", "Isolated Stop", 28.7000, 77.3000),
    }

    routes = {
        "R1": Route("R1", RouteType.BUS, route_short_name="101"),
        "R2": Route("R2", RouteType.BUS, route_short_name="102"),
    }

    calendar = {
        "CAL_ALL": CalendarService(
            service_id="CAL_ALL",
            monday=True, tuesday=True, wednesday=True, thursday=True,
            friday=True, saturday=True, sunday=True,
            start_date=date(2022, 1, 1),
            end_date=date(2025, 1, 1),
        )
    }

    trips = {
        "T1": Trip("T1", "R1", "CAL_ALL"),
        "T2": Trip("T2", "R2", "CAL_ALL"),
    }

    stop_times = {
        "T1": [
            StopTime("T1", "A", 1, 8 * 3600, 8 * 3600),
            StopTime("T1", "B", 2, 8 * 3600 + 900, 8 * 3600 + 900),
            StopTime("T1", "C", 3, 8 * 3600 + 1800, 8 * 3600 + 1800),
        ],
        "T2": [
            StopTime("T2", "C", 1, 8 * 3600 + 2100, 8 * 3600 + 2100),  # 08:35:00
            StopTime("T2", "D", 2, 9 * 3600, 9 * 3600),                # 09:00:00
        ],
    }

    dataset = GTFSDataset(
        feed_info=None,
        agencies={},
        stops=stops,
        routes=routes,
        trips=trips,
        stop_times=stop_times,
        calendar=calendar,
        calendar_dates={},
        shapes={},
        transfers=[],
        fare_attributes={},
        fare_rules=[],
        source_id="test_fixture",
    )

    graph = GraphBuilder.build_graph(dataset, enable_walking=False)
    router = RoutingEngine(dataset, graph)
    return dataset, graph, router


def test_direct_route_planning(mini_transit_network):
    dataset, graph, router = mini_transit_network
    journeys, reason = router.plan_journey(
        origin_stop_id="A",
        destination_stop_id="C",
        departure_date=date(2024, 6, 1),
        departure_seconds=7 * 3600 + 50 * 60,  # 07:50:00
    )
    assert reason is None
    assert len(journeys) >= 1
    j = journeys[0]
    assert j.departure_time_str == "08:00:00"
    assert j.arrival_time_str == "08:30:00"
    assert j.num_transfers == 0
    assert len(j.legs) == 1
    assert j.legs[0].from_stop_id == "A"
    assert j.legs[0].to_stop_id == "C"


def test_transfer_route_planning(mini_transit_network):
    dataset, graph, router = mini_transit_network
    journeys, reason = router.plan_journey(
        origin_stop_id="A",
        destination_stop_id="D",
        departure_date=date(2024, 6, 1),
        departure_seconds=7 * 3600 + 55 * 60,
    )
    assert reason is None
    assert len(journeys) >= 1
    j = journeys[0]
    assert j.departure_time_str == "08:00:00"
    assert j.arrival_time_str == "09:00:00"
    assert j.num_transfers == 1


def test_unreachable_destination(mini_transit_network):
    dataset, graph, router = mini_transit_network
    journeys, reason = router.plan_journey(
        origin_stop_id="A",
        destination_stop_id="ISO",
        departure_date=date(2024, 6, 1),
        departure_seconds=8 * 3600,
    )
    assert len(journeys) == 0
    assert reason is not None
    assert "No feasible transit route found" in reason


def test_unknown_fare_not_treated_as_zero(mini_transit_network):
    dataset, graph, router = mini_transit_network
    # Invalidate stop coordinates to simulate unavailable stop coordinates where distance cannot be determined
    dataset.stops["A"].stop_lat = None
    journeys, _ = router.plan_journey(
        origin_stop_id="A",
        destination_stop_id="C",
        departure_date=date(2024, 6, 1),
        departure_seconds=8 * 3600,
    )
    assert len(journeys) >= 1
    j = journeys[0]
    # In feeds without fare data or coordinates, fare must be None and fare_complete False
    assert j.total_fare_inr is None
    assert j.fare_complete is False
    assert any("Fare information is not available" in w for w in j.warnings)


def test_impossible_connection_past_departure(mini_transit_network):
    dataset, graph, router = mini_transit_network
    # Requesting departure at 08:35:00 at stop A (trip departed at 08:00:00)
    journeys, reason = router.plan_journey(
        origin_stop_id="A",
        destination_stop_id="C",
        departure_date=date(2024, 6, 1),
        departure_seconds=8 * 3600 + 35 * 60,
    )
    assert len(journeys) == 0
    assert reason is not None


def test_origin_equals_destination(mini_transit_network):
    _, _, router = mini_transit_network
    journeys, reason = router.plan_journey(
        origin_stop_id="A",
        destination_stop_id="A",
        departure_date=date(2024, 6, 1),
        departure_seconds=8 * 3600,
    )
    assert len(journeys) == 0
    assert reason == "Origin and destination stops are identical."


def test_invalid_or_unknown_stop_ids(mini_transit_network):
    _, _, router = mini_transit_network
    journeys, reason = router.plan_journey(
        origin_stop_id="NONEXISTENT_ORIGIN",
        destination_stop_id="C",
        departure_date=date(2024, 6, 1),
        departure_seconds=8 * 3600,
    )
    assert len(journeys) == 0
    assert "Origin stop 'NONEXISTENT_ORIGIN' does not exist" in reason

    journeys, reason = router.plan_journey(
        origin_stop_id="A",
        destination_stop_id="NONEXISTENT_DEST",
        departure_date=date(2024, 6, 1),
        departure_seconds=8 * 3600,
    )
    assert len(journeys) == 0
    assert "Destination stop 'NONEXISTENT_DEST' does not exist" in reason


def test_multiple_transfers_and_max_transfers_cutoff():
    """Network: A -> B (T1), B -> C (T2), C -> D (T3). Requires 2 transfers."""
    stops = {
        "A": Stop("A", "Stop A", 28.61, 77.21),
        "B": Stop("B", "Stop B", 28.62, 77.22),
        "C": Stop("C", "Stop C", 28.63, 77.23),
        "D": Stop("D", "Stop D", 28.64, 77.24),
    }
    routes = {
        "R1": Route("R1", RouteType.BUS),
        "R2": Route("R2", RouteType.BUS),
        "R3": Route("R3", RouteType.BUS),
    }
    calendar = {
        "C1": CalendarService("C1", True, True, True, True, True, True, True, date(2024, 1, 1), date(2025, 1, 1))
    }
    trips = {
        "T1": Trip("T1", "R1", "C1"),
        "T2": Trip("T2", "R2", "C1"),
        "T3": Trip("T3", "R3", "C1"),
    }
    stop_times = {
        "T1": [StopTime("T1", "A", 1, 28800, 28800), StopTime("T1", "B", 2, 29400, 29400)], # 08:00 to 08:10
        "T2": [StopTime("T2", "B", 1, 29600, 29600), StopTime("T2", "C", 2, 30200, 30200)], # 08:13:20 to 08:23:20
        "T3": [StopTime("T3", "C", 1, 30500, 30500), StopTime("T3", "D", 2, 31200, 31200)], # 08:28:20 to 08:40
    }
    dataset = GTFSDataset(None, {}, stops, routes, trips, stop_times, calendar, {}, {}, [], {}, [], source_id="test")
    graph = GraphBuilder.build_graph(dataset, enable_walking=False)
    router = RoutingEngine(dataset, graph)

    # 1. Allowed 2 transfers: Journey should succeed
    journeys, reason = router.plan_journey("A", "D", date(2024, 6, 1), 28800, max_transfers=2)
    assert reason is None
    assert len(journeys) == 1
    assert journeys[0].num_transfers == 2
    assert len(journeys[0].legs) == 3

    # 2. Allowed only 1 transfer: Should fail as 2 are required
    journeys_restricted, reason_restricted = router.plan_journey("A", "D", date(2024, 6, 1), 28800, max_transfers=1)
    assert len(journeys_restricted) == 0
    assert reason_restricted is not None


def test_transfer_buffer_enforced():
    """Connecting trip departs within 60s of arrival (below 120s buffer) -> should not be boarded."""
    stops = {"A": Stop("A", "Stop A", 28.61, 77.21), "B": Stop("B", "Stop B", 28.62, 77.22), "C": Stop("C", "Stop C", 28.63, 77.23)}
    routes = {"R1": Route("R1", RouteType.BUS), "R2": Route("R2", RouteType.BUS)}
    calendar = {"C1": CalendarService("C1", True, True, True, True, True, True, True, date(2024, 1, 1), date(2025, 1, 1))}
    trips = {"T1": Trip("T1", "R1", "C1"), "T2": Trip("T2", "R2", "C1")}
    # T1 arrives at B at 08:10:00 (29400s). T2 departs B at 08:11:00 (29460s) -> only 60s buffer!
    stop_times = {
        "T1": [StopTime("T1", "A", 1, 28800, 28800), StopTime("T1", "B", 2, 29400, 29400)],
        "T2": [StopTime("T2", "B", 1, 29460, 29460), StopTime("T2", "C", 2, 30000, 30000)],
    }
    dataset = GTFSDataset(None, {}, stops, routes, trips, stop_times, calendar, {}, {}, [], {}, [], source_id="test")
    graph = GraphBuilder.build_graph(dataset, enable_walking=False)
    router = RoutingEngine(dataset, graph)

    journeys, reason = router.plan_journey("A", "C", date(2024, 6, 1), 28800)
    assert len(journeys) == 0
    assert "No feasible transit route found" in reason


def test_overnight_gtfs_time_beyond_24_hours():
    """GTFS trip operating past midnight, e.g., 24:30:00 (00:30 next day)."""
    stops = {"A": Stop("A", "Stop A", 28.61, 77.21), "B": Stop("B", "Stop B", 28.62, 77.22)}
    routes = {"R1": Route("R1", RouteType.BUS)}
    calendar = {"C1": CalendarService("C1", True, True, True, True, True, True, True, date(2024, 1, 1), date(2025, 1, 1))}
    trips = {"T1": Trip("T1", "R1", "C1")}
    dep_sec = 24 * 3600 + 30 * 60  # 24:30:00 (88200)
    arr_sec = 25 * 3600 + 15 * 60  # 25:15:00 (90900)
    stop_times = {"T1": [StopTime("T1", "A", 1, dep_sec, dep_sec), StopTime("T1", "B", 2, arr_sec, arr_sec)]}
    dataset = GTFSDataset(None, {}, stops, routes, trips, stop_times, calendar, {}, {}, [], {}, [], source_id="test")
    graph = GraphBuilder.build_graph(dataset, enable_walking=False)
    router = RoutingEngine(dataset, graph)

    # Search starting at 24:00:00
    journeys, reason = router.plan_journey("A", "B", date(2024, 6, 1), 24 * 3600)
    assert reason is None
    assert len(journeys) == 1
    assert journeys[0].departure_time_str == "24:30:00"
    assert journeys[0].arrival_time_str == "25:15:00"
    assert journeys[0].total_duration_seconds == 45 * 60


def test_calendar_weekday_and_exception_handling():
    """Verify service calendar day-of-week and calendar_dates exceptions."""
    stops = {"A": Stop("A", "Stop A", 28.61, 77.21), "B": Stop("B", "Stop B", 28.62, 77.22)}
    routes = {"R1": Route("R1", RouteType.BUS)}
    # Weekday-only service (Mon-Fri)
    calendar = {
        "WEEKDAY": CalendarService("WEEKDAY", True, True, True, True, True, False, False, date(2024, 1, 1), date(2024, 12, 31))
    }
    # Exception: Service removed on 2024-06-03 (a Monday)
    calendar_dates = {
        "WEEKDAY": [CalendarDate("WEEKDAY", date(2024, 6, 3), ExceptionType.SERVICE_REMOVED)]
    }
    trips = {"T1": Trip("T1", "R1", "WEEKDAY")}
    stop_times = {"T1": [StopTime("T1", "A", 1, 28800, 28800), StopTime("T1", "B", 2, 29400, 29400)]}
    dataset = GTFSDataset(None, {}, stops, routes, trips, stop_times, calendar, calendar_dates, {}, [], {}, [], source_id="test")
    graph = GraphBuilder.build_graph(dataset, enable_walking=False)
    router = RoutingEngine(dataset, graph)

    # 1. Active Monday: 2024-06-10 (operates)
    journeys_active, _ = router.plan_journey("A", "B", date(2024, 6, 10), 28800)
    assert len(journeys_active) == 1

    # 2. Inactive Sunday: 2024-06-09 (no Sunday service)
    journeys_sunday, reason_sunday = router.plan_journey("A", "B", date(2024, 6, 9), 28800)
    assert len(journeys_sunday) == 0
    assert "No scheduled transit services operate" in reason_sunday

    # 3. Exception date: 2024-06-03 (Monday, but SERVICE_REMOVED)
    journeys_exception, reason_exception = router.plan_journey("A", "B", date(2024, 6, 3), 28800)
    assert len(journeys_exception) == 0
    assert "No scheduled transit services operate" in reason_exception


def test_multiple_candidate_trips_distinct_departures():
    """Route with 3 trips departing at 08:00, 08:20, and 08:45."""
    stops = {"A": Stop("A", "Stop A", 28.61, 77.21), "B": Stop("B", "Stop B", 28.62, 77.22)}
    routes = {"R1": Route("R1", RouteType.BUS)}
    calendar = {"C1": CalendarService("C1", True, True, True, True, True, True, True, date(2024, 1, 1), date(2025, 1, 1))}
    trips = {"T1": Trip("T1", "R1", "C1"), "T2": Trip("T2", "R1", "C1"), "T3": Trip("T3", "R1", "C1")}
    stop_times = {
        "T1": [StopTime("T1", "A", 1, 8 * 3600, 8 * 3600), StopTime("T1", "B", 2, 8 * 3600 + 1200, 8 * 3600 + 1200)],
        "T2": [StopTime("T2", "A", 1, 8 * 3600 + 1200, 8 * 3600 + 1200), StopTime("T2", "B", 2, 8 * 3600 + 2400, 8 * 3600 + 2400)],
        "T3": [StopTime("T3", "A", 1, 8 * 3600 + 2700, 8 * 3600 + 2700), StopTime("T3", "B", 2, 8 * 3600 + 3900, 8 * 3600 + 3900)],
    }
    dataset = GTFSDataset(None, {}, stops, routes, trips, stop_times, calendar, {}, {}, [], {}, [], source_id="test")
    graph = GraphBuilder.build_graph(dataset, enable_walking=False)
    router = RoutingEngine(dataset, graph)

    journeys, reason = router.plan_journey("A", "B", date(2024, 6, 1), 7 * 3600 + 50 * 60, max_candidates=3)
    assert reason is None
    assert len(journeys) >= 2
    deps = [j.departure_time_str for j in journeys]
    assert "08:00:00" in deps
    assert "08:20:00" in deps


def test_chronological_ordering_and_totals_integrity():
    """Verify that every journey has chronological legs and accurate total metrics."""
    stops = {
        "A": Stop("A", "Stop A", 28.61, 77.21),
        "B": Stop("B", "Stop B", 28.62, 77.22),
        "C": Stop("C", "Stop C", 28.63, 77.23),
    }
    routes = {"R1": Route("R1", RouteType.BUS), "R2": Route("R2", RouteType.BUS)}
    calendar = {"C1": CalendarService("C1", True, True, True, True, True, True, True, date(2024, 1, 1), date(2025, 1, 1))}
    trips = {"T1": Trip("T1", "R1", "C1"), "T2": Trip("T2", "R2", "C1")}
    stop_times = {
        "T1": [StopTime("T1", "A", 1, 28800, 28800), StopTime("T1", "B", 2, 29400, 29400)], # 08:00 to 08:10
        "T2": [StopTime("T2", "B", 1, 29700, 29700), StopTime("T2", "C", 2, 30600, 30600)], # 08:15 to 08:30
    }
    dataset = GTFSDataset(None, {}, stops, routes, trips, stop_times, calendar, {}, {}, [], {}, [], source_id="test")
    graph = GraphBuilder.build_graph(dataset, enable_walking=False)
    router = RoutingEngine(dataset, graph)

    journeys, _ = router.plan_journey("A", "C", date(2024, 6, 1), 28000)
    assert len(journeys) == 1
    j = journeys[0]

    # Verify chronological sequence
    assert RoutingEngine._validate_leg_chronology(j.legs) is True
    assert j.legs[0].departure_seconds <= j.legs[0].arrival_seconds
    assert j.legs[0].arrival_seconds <= j.legs[1].departure_seconds
    assert j.legs[1].departure_seconds <= j.legs[1].arrival_seconds

    # Verify totals
    assert j.total_duration_seconds == (30600 - 28800)  # 1800s (30 mins transit duration)
    assert j.initial_wait_seconds == (28800 - 28000)   # 800s wait before boarding
    assert j.num_transfers == 1
    assert j.total_walk_meters == 0.0


def test_walking_transfer_multimodal_journey():
    """Verify walking transfer connecting two disjoint routes."""
    # Stop A -> Stop B (Trip 1)
    # Stop B and Stop C are within 200m (lat/lon diff ~0.001 deg)
    # Stop C -> Stop D (Trip 2)
    stops = {
        "A": Stop("A", "Stop A", 28.6100, 77.2100),
        "B": Stop("B", "Stop B", 28.6200, 77.2200),
        "C": Stop("C", "Stop C", 28.6210, 77.2210),  # ~150m from B
        "D": Stop("D", "Stop D", 28.6300, 77.2300),
    }
    routes = {"R1": Route("R1", RouteType.BUS), "R2": Route("R2", RouteType.BUS)}
    calendar = {"C1": CalendarService("C1", True, True, True, True, True, True, True, date(2024, 1, 1), date(2025, 1, 1))}
    trips = {"T1": Trip("T1", "R1", "C1"), "T2": Trip("T2", "R2", "C1")}
    stop_times = {
        "T1": [StopTime("T1", "A", 1, 28800, 28800), StopTime("T1", "B", 2, 29400, 29400)], # arr B 08:10:00
        # Walk B -> C takes ~120s, arrival ~08:12:00
        "T2": [StopTime("T2", "C", 1, 29700, 29700), StopTime("T2", "D", 2, 30600, 30600)], # dep C 08:15:00
    }
    dataset = GTFSDataset(None, {}, stops, routes, trips, stop_times, calendar, {}, {}, [], {}, [], source_id="test")
    graph = GraphBuilder.build_graph(dataset, max_walk_transfer_meters=300.0, enable_walking=True)
    assert graph.total_walk_edges > 0

    router = RoutingEngine(dataset, graph)
    journeys, reason = router.plan_journey("A", "D", date(2024, 6, 1), 28800)
    assert reason is None
    assert len(journeys) >= 1
    j = journeys[0]
    modes = [l.mode for l in j.legs]
    assert LegMode.WALK in modes
    assert j.total_walk_meters > 0.0


