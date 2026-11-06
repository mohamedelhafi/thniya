package tn.thniya.api.itinerary;

import jakarta.validation.Valid;

import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import tn.thniya.api.common.Lang;
import tn.thniya.api.itinerary.ItineraryModels.DepartureChoice;
import tn.thniya.api.itinerary.ItineraryModels.ItinerariesResponse;
import tn.thniya.api.itinerary.ItineraryModels.ItineraryRequest;
import tn.thniya.api.itinerary.ItineraryModels.ItineraryView;

@RestController
@RequestMapping("/api/v1/itineraries")
public class ItineraryController {

	private final ItineraryService service;

	public ItineraryController(ItineraryService service) {
		this.service = service;
	}

	@PostMapping
	public ItinerariesResponse plan(@Valid @RequestBody ItineraryRequest request, Lang lang) {
		return service.plan(request, lang);
	}

	/** Choisir un autre départ pour un segment (puces « autres départs » de la fiche trajet). */
	@PostMapping("/{id}/legs/{index}/departures")
	public ItineraryView otherDeparture(@PathVariable String id, @PathVariable int index,
			@Valid @RequestBody DepartureChoice choice) {
		return service.alternative(id, index, choice);
	}

}
