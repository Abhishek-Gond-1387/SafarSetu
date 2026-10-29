"""Unit tests for public transport routing engine and ranking algorithms."""
from datetime import date
import pytest

from app.models.journey import LegMode, RouteRankCriterion
from app.models.transit import (
    CalendarService,
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
    journeys, _ = router.plan_journey(
        origin_stop_id="A",
        destination_stop_id="C",
        departure_date=date(2024, 6, 1),
        departure_seconds=8 * 3600,
    )
    assert len(journeys) >= 1
    j = journeys[0]
    # In genuine feeds without fare data, fare must be None and fare_complete False
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

