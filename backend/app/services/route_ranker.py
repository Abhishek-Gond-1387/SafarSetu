"""Route ranking and comparison service."""
from __future__ import annotations

from typing import List, Optional, Tuple

from app.models.journey import Journey, RouteRankCriterion
from app.schemas.routing import JourneyOut, RouteCompareMetrics, RouteCompareResponse


class RouteRanker:
    """Ranks and compares candidate journey alternatives."""

    @classmethod
    def rank(
        cls,
        journeys: List[Journey],
        criterion: RouteRankCriterion = RouteRankCriterion.FASTEST,
    ) -> List[Journey]:
        if not journeys:
            return []

        if criterion == RouteRankCriterion.FASTEST:
            return sorted(journeys, key=lambda j: j.total_duration_seconds)

        elif criterion == RouteRankCriterion.CHEAPEST:
            # Rule: Feeds with unknown fare must not be sorted as 0!
            # Separate complete vs incomplete
            complete = [j for j in journeys if j.fare_complete and j.total_fare_inr is not None]
            incomplete = [j for j in journeys if not j.fare_complete]
            sorted_complete = sorted(complete, key=lambda j: j.total_fare_inr or float("inf"))
            return sorted_complete + incomplete

        elif criterion == RouteRankCriterion.BALANCED:
            # Weighted score: time_min + 1.5 * transfers + 0.01 * walk_m
            def balanced_score(j: Journey) -> float:
                mins = j.total_duration_seconds / 60.0
                return mins + (1.5 * j.num_transfers) + (0.01 * j.total_walk_meters)

            return sorted(journeys, key=balanced_score)

        return journeys

    @classmethod
    def compare(cls, journeys: List[JourneyOut]) -> RouteCompareResponse:
        """Compare client-submitted journey candidates using server-evaluated metrics."""
        # 1. Rank by duration (fastest)
        by_duration = sorted(range(len(journeys)), key=lambda i: journeys[i].total_duration_minutes)
        rank_fastest_map = {orig_idx: rank + 1 for rank, orig_idx in enumerate(by_duration)}

        # 2. Rank by fare (cheapest) — only for complete fares
        has_complete_fare = any(j.fare_complete and j.fare_inr is not None for j in journeys)
        rank_cheapest_map = {}
        if has_complete_fare:
            fare_candidates = [
                (i, journeys[i].fare_inr)
                for i in range(len(journeys))
                if journeys[i].fare_complete and journeys[i].fare_inr is not None
            ]
            fare_candidates.sort(key=lambda x: x[1])
            for rank, (orig_idx, _) in enumerate(fare_candidates):
                rank_cheapest_map[orig_idx] = rank + 1

        # 3. Rank by balanced score
        def balanced_score(j: JourneyOut) -> float:
            return j.total_duration_minutes + (1.5 * j.num_transfers) + (0.01 * j.total_walk_meters)

        by_balanced = sorted(range(len(journeys)), key=lambda i: balanced_score(journeys[i]))
        rank_balanced_map = {orig_idx: rank + 1 for rank, orig_idx in enumerate(by_balanced)}

        metrics_list: List[RouteCompareMetrics] = []
        for i, j in enumerate(journeys):
            recs = []
            if rank_fastest_map.get(i) == 1:
                recs.append("Fastest option")
            if rank_cheapest_map.get(i) == 1:
                recs.append("Cheapest option")
            if rank_balanced_map.get(i) == 1:
                recs.append("Best balance of time and transfers")

            recommendation = ", ".join(recs) if recs else "Alternative option"

            metrics_list.append(
                RouteCompareMetrics(
                    duration_minutes=j.total_duration_minutes,
                    walk_meters=j.total_walk_meters,
                    num_transfers=j.num_transfers,
                    fare_inr=j.fare_inr,
                    fare_complete=j.fare_complete,
                    rank_fastest=rank_fastest_map[i],
                    rank_cheapest=rank_cheapest_map.get(i),
                    rank_balanced=rank_balanced_map[i],
                    recommendation=recommendation,
                )
            )

        return RouteCompareResponse(
            journeys=journeys,
            metrics=metrics_list,
        )

