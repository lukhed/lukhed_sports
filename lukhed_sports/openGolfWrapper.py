import json
from urllib.parse import urlencode
from lukhed_basic_utils import classCommon
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils import timeCommon as tC

"""
Documentation:
    https://github.com/opengolfapi/api
    https://opengolfapi.org
    Full spec: https://api.opengolfapi.org/openapi.json
"""

class OpenGolfApi(classCommon.LukhedAuth):
    """
    Custom wrapper for OpenGolfAPI (https://opengolfapi.org) - golf's open data standard: course data for
    all US courses, scorecards, tee ratings, live weather, climate, scoring engine, competitions,
    shot/moment contribution, and more.

    Do I need an API key?
    ---------------------
    Probably not. Per the API docs: "Reads work without a key - 1,000 requests/day per IP, plus gross
    scoring is keyless. No signup to try it." That means everything read-only in this class (courses,
    weather, spatial features, orgs, chain, meta, etc.) AND the gross scoring engine
    (compute_score/compute_plays_like) work with a plain ``OpenGolfApi()`` - no key, no signup.

    A free dev key (https://opengolfapi.org/developer) is only needed for the write/contribution
    surface: methods whose docstrings say "Requires API key" (posting shots/moments, corrections,
    creating competitions/events, webhooks, minting assets, reading back your own contributed data,
    etc.). Those methods raise a helpful ValueError if no key is set, so you won't waste a call.

    Note per the API docs: if a key IS sent it must be valid and verified (there is no anonymous
    fallback for a bad key). This class sends your key on all calls when one is configured, so only
    configure a real, verified key.

    Usage
    -----
    Keyless (all reads + gross scoring; 1,000 requests/day per IP)::

        golf = OpenGolfApi()
        courses = golf.search_courses(q="pebble beach")

    With an API key managed by lukhed key management (prompts for key on first use)::

        golf = OpenGolfApi(key_management='github')   # or 'local'

    With an API key provided directly (e.g., website backend pulling key from its own secret store)::

        golf = OpenGolfApi(auth_dict={'key': 'ogapi_...'})

    After any call, the raw requests.Response is available at ``self.latest_response`` for status
    code/header inspection.
    """

    def __init__(self, api_delay=0, key_management=None, auth_dict=None, opengolf_token=None, timeout=10):
        """
        Initializes the OpenGolfApi wrapper.

        Parameters
        ----------
        api_delay : int or float, optional
            Delay in seconds between API calls, by default 0. The published keyless limit is a daily
            quota (1,000 requests/day per IP), not a per-second rate, so no delay is needed by default.
        key_management : str, optional
            None (default) for keyless use - all read endpoints (1,000 requests/day per IP) and gross
            scoring work without a key. Only set this if you need the write/contribution endpoints
            (methods documented with "Requires API key"). 'local' to store your API key on your local
            hardware. 'github' to store it in your private github repository (you will need a github
            account and github token). When 'local' or 'github' is used and no key is stored yet, you
            will be walked through setup via command prompts.
        auth_dict : dict, optional
            Provide your auth data directly to skip storage/setup, e.g. {'key': 'ogapi_...'}. Useful
            for server environments where interactive setup is not possible. If key_management is also
            set, the provided dict is stored per your preference.
        opengolf_token : str, optional
            An OpenGolf ID access token (from the oauth flow) used for identity endpoints
            (developer keys/apps). Can also be set later via set_opengolf_token().
        timeout : int, optional
            Request timeout in seconds, by default 10.
        """
        self.api_delay = api_delay
        self._timeout = timeout
        self._base_url = "https://api.opengolfapi.org"
        self._call_counter = 0
        self._opengolf_token = opengolf_token
        self.latest_response = None

        if key_management is not None:
            super().__init__('openGolfApi', key_management=key_management)
            if auth_dict is not None:
                self._auth_data = auth_dict
                self.kM.force_update_key_data(self._auth_data)
            if self._auth_data is None:
                self._auth_setup()
            self._api_key = self._auth_data['key']
        else:
            self._api_key = auth_dict.get('key') if auth_dict is not None else None

    def _auth_setup(self):
        """
        Set up OpenGolfAPI authentication (interactive).
        """
        input("Note: OpenGolfAPI reads (1,000 requests/day per IP) and gross scoring are free WITHOUT a key - "
              "you only need a key for write/contribution endpoints (posting shots/moments, corrections, "
              "competitions, webhooks, etc.). If that's you, get a free key at https://opengolfapi.org/developer. "
              "You will be asked to paste your key in the next step. It will be stored for future use based on "
              "your instantiation parameters (stored on local machine or your private github). "
              "Press enter to start.")
        key = input("Enter key: ")

        self._auth_data = {
            "key": key.strip()
        }

        # Write auth data to user specified storage
        self.kM.force_update_key_data(self._auth_data)
        print("Authentication has been set up successfully.")

    def set_opengolf_token(self, token):
        """
        Set the OpenGolf ID access token (X-OpenGolf-Token) used by identity-backed developer endpoints.
        Obtain one via oauth_start() -> oauth_submit_code() -> oauth_exchange_token().

        Parameters
        ----------
        token : str
            OpenGolf access token.
        """
        self._opengolf_token = token

    def _require_key(self):
        if self._api_key is None:
            raise ValueError("This endpoint requires an OpenGolfAPI key. Get a free key at "
                             "https://opengolfapi.org/developer, then instantiate the class with "
                             "auth_dict={'key': 'ogapi_...'} or key_management='local'/'github'.")

    def _require_token(self):
        if self._opengolf_token is None:
            raise ValueError("This endpoint requires an OpenGolf ID access token (X-OpenGolf-Token). "
                             "Complete the sign-in flow (oauth_start -> oauth_submit_code -> "
                             "oauth_exchange_token) then call set_opengolf_token().")

    @staticmethod
    def _clean_params(params):
        """
        Drop None values and convert booleans to lowercase strings for query encoding.
        """
        if params is None:
            return {}
        cleaned = {}
        for k, v in params.items():
            if v is None:
                continue
            if isinstance(v, bool):
                v = 'true' if v else 'false'
            cleaned[k] = v
        return cleaned

    def _make_api_call(self, endpoint, method="GET", params=None, body=None, keyed=False, token=False,
                       extra_headers=None, raw_body=None, content_type=None, return_text=False):
        """
        Use this method to make all API calls so delays, auth headers, and parsing are handled uniformly.

        Parameters
        ----------
        endpoint : str
            Path portion of the url, e.g. '/api/v1/courses/search'
        method : str, optional
            HTTP method, by default "GET"
        params : dict, optional
            Query string parameters (None values are dropped), by default None
        body : dict or list, optional
            JSON body for write requests, by default None
        keyed : bool, optional
            True if the endpoint requires an API key (raises helpful error when no key), by default False
        token : bool, optional
            True if the endpoint requires an X-OpenGolf-Token, by default False
        extra_headers : dict, optional
            Any additional headers, by default None
        raw_body : str, optional
            Raw (non-json) request body, e.g. GPX/CSV content, by default None
        content_type : str, optional
            Content type for raw_body, by default None
        return_text : bool, optional
            True to return response text instead of parsed json (e.g. SVG/HTML endpoints),
            by default False

        Returns
        -------
        dict or list or str
            Parsed json response, or response text when return_text is True or json parsing fails.
        """
        if self._call_counter > 0 and self.api_delay:
            tC.sleep(self.api_delay)

        url = self._base_url + endpoint
        query = self._clean_params(params)
        if query:
            url = url + "?" + urlencode(query)

        headers = {}
        if keyed:
            self._require_key()
        if self._api_key is not None:
            headers['X-API-Key'] = self._api_key
        if token:
            self._require_token()
            headers['X-OpenGolf-Token'] = self._opengolf_token
        if extra_headers:
            headers.update(extra_headers)

        data = {}
        if body is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(body)
        elif raw_body is not None:
            if content_type is not None:
                headers['Content-Type'] = content_type
            data = raw_body

        r = rC.make_request(url, method=method, headers=headers, params=data, timeout=self._timeout)
        self.latest_response = r
        self._call_counter = self._call_counter + 1

        if return_text:
            return r.text
        try:
            return r.json()
        except ValueError:
            return r.text

    ####################
    # Meta - service info, docs, and schemas (free, keyless)
    def get_service_info(self):
        """
        Service info & endpoint list.

        Endpoint: GET /

        Returns
        -------
        dict
        """
        return self._make_api_call("/")

    def get_health(self):
        """
        Health check.

        Endpoint: GET /api/v1/health

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/health")

    def get_stats(self):
        """
        Live dataset stats (course counts).

        Endpoint: GET /api/v1/stats

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/stats")

    def get_ontology(self):
        """
        The ontology - all moment types, payload schemas, broadcast kinds, icon vocabulary (free, CC0).

        Endpoint: GET /api/v1/ontology

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/ontology")

    def get_domain_model(self):
        """
        The domain model - canonical entity definitions (course/hole/player/session/competition/event),
        player_id rules, score-pipeline router, error contract.

        Endpoint: GET /api/v1/model

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/model")

    def get_capabilities(self):
        """
        Generated map of the open platform (standards, formats, moment types, endpoints).

        Endpoint: GET /api/v1/capabilities

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/capabilities")

    def get_primitives(self):
        """
        The 15-primitive ontology (one vocabulary for the whole platform).

        Endpoint: GET /api/v1/primitives

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/primitives")

    def get_openapi_spec(self):
        """
        The OpenAPI spec for the API.

        Endpoint: GET /openapi.json

        Returns
        -------
        dict
        """
        return self._make_api_call("/openapi.json")

    def get_asyncapi_spec(self):
        """
        AsyncAPI 3.0 doc for the webhook event stream.

        Endpoint: GET /asyncapi.json

        Returns
        -------
        dict
        """
        return self._make_api_call("/asyncapi.json")

    def get_llms_txt(self):
        """
        AI-facing usage guide (llmstxt.org).

        Endpoint: GET /llms.txt

        Returns
        -------
        str
        """
        return self._make_api_call("/llms.txt", return_text=True)

    def get_langchain_adapter(self):
        """
        LangChain tool manifest (generated from the OpenAPI spec).

        Endpoint: GET /adapters/langchain.json

        Returns
        -------
        dict
        """
        return self._make_api_call("/adapters/langchain.json")

    def get_zapier_adapter(self):
        """
        Zapier app definition (generated from the OpenAPI spec + events).

        Endpoint: GET /adapters/zapier.json

        Returns
        -------
        dict
        """
        return self._make_api_call("/adapters/zapier.json")

    def get_openshot_fields(self):
        """
        OpenShot field catalog (what to send when contributing shots).

        Endpoint: GET /api/v1/openshot/fields

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/openshot/fields")

    def get_moments_fields(self):
        """
        Moments field catalog (canonical payload fields per moment_type).

        Endpoint: GET /api/v1/moments/fields

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/moments/fields")

    def get_oidc_configuration(self):
        """
        OIDC discovery document for Sign in with OpenGolf.

        Endpoint: GET /.well-known/openid-configuration

        Returns
        -------
        dict
        """
        return self._make_api_call("/.well-known/openid-configuration")

    ####################
    # Toolkit (free, keyless unless noted)
    def validate_payload(self, validation_request):
        """
        Validate a payload against an inline JSON Schema.

        Endpoint: POST /api/v1/toolkit/validate

        Parameters
        ----------
        validation_request : dict
            Object containing the schema and payload to validate.

        Returns
        -------
        dict
            {valid, errors}
        """
        return self._make_api_call("/api/v1/toolkit/validate", method="POST", body=validation_request)

    def get_badge(self):
        """
        "Built on OpenGolf" SVG badge.

        Endpoint: GET /api/v1/toolkit/badge

        Returns
        -------
        str
            SVG content.
        """
        return self._make_api_call("/api/v1/toolkit/badge", return_text=True)

    def convert_app_endpoints(self, conversion_request):
        """
        Scaffold an adapter from your app's endpoints.

        Endpoint: POST /api/v1/toolkit/convert

        Parameters
        ----------
        conversion_request : dict
            Your app's endpoint description.

        Returns
        -------
        dict
            Adapter scaffold + AI prompt.
        """
        return self._make_api_call("/api/v1/toolkit/convert", method="POST", body=conversion_request)

    def get_quickstart(self):
        """
        The all-in-one build recipe (identity -> corpus -> score -> contribute -> chain).

        Endpoint: GET /api/v1/toolkit/quickstart

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/toolkit/quickstart")

    def get_playground(self):
        """
        Copy-paste recipes for the free surface.

        Endpoint: GET /api/v1/toolkit/playground

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/toolkit/playground")

    def get_playground_html(self):
        """
        Interactive browser playground.

        Endpoint: GET /api/v1/toolkit/playground.html

        Returns
        -------
        str
            HTML content.
        """
        return self._make_api_call("/api/v1/toolkit/playground.html", return_text=True)

    def get_built_with_showcase(self):
        """
        The "Built with OpenGolf" showcase.

        Endpoint: GET /api/v1/toolkit/built-with

        Returns
        -------
        dict
            apps[]
        """
        return self._make_api_call("/api/v1/toolkit/built-with")

    def register_app_in_showcase(self, app_info):
        """
        Register your app in the "Built with OpenGolf" showcase. Requires API key.

        Endpoint: POST /api/v1/toolkit/built-with

        Parameters
        ----------
        app_info : dict
            Your app's info.

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/toolkit/built-with", method="POST", body=app_info, keyed=True)

    ####################
    # Courses (free, keyless)
    def search_courses(self, q=None, state=None, lat=None, lng=None, radius_mi=None, course_type=None,
                       limit=None, offset=None):
        """
        Search courses by name, state, or location.

        Endpoint: GET /api/v1/courses/search

        Parameters
        ----------
        q : str, optional
            Course name search.
        state : str, optional
            2-letter US state code.
        lat : float, optional
            Latitude (with lng) for radius search.
        lng : float, optional
            Longitude (with lat).
        radius_mi : float, optional
            Search radius in miles, API default 25.
        course_type : str, optional
            Course type filter.
        limit : int, optional
            API default 25.
        offset : int, optional
            API default 0.

        Returns
        -------
        dict
            {courses: [...], total: int}. distance_mi present only on lat/lng searches.
        """
        params = {'q': q, 'state': state, 'lat': lat, 'lng': lng, 'radius_mi': radius_mi,
                  'type': course_type, 'limit': limit, 'offset': offset}
        return self._make_api_call("/api/v1/courses/search", params=params)

    def get_courses_by_state(self, state_code, limit=None, offset=None):
        """
        All courses in a US state.

        Endpoint: GET /api/v1/courses/state/{code}

        Parameters
        ----------
        state_code : str
            2-letter state code.
        limit : int, optional
        offset : int, optional

        Returns
        -------
        dict
            {courses: [...], total: int}
        """
        params = {'limit': limit, 'offset': offset}
        return self._make_api_call(f"/api/v1/courses/state/{state_code}", params=params)

    def get_courses_by_architect(self, architect_name):
        """
        Courses by architect (fuzzy match).

        Endpoint: GET /api/v1/courses/architect/{name}

        Parameters
        ----------
        architect_name : str
            Architect name, e.g. 'donald ross'.

        Returns
        -------
        dict
            {courses: [...], total: int}
        """
        return self._make_api_call(f"/api/v1/courses/architect/{architect_name}")

    def get_courses_bulk(self, course_ids):
        """
        Batch fetch courses by id (max 100).

        Endpoint: GET /api/v1/courses/bulk

        Parameters
        ----------
        course_ids : list or str
            List of course ids (or a pre-joined comma-separated string), max 100.

        Returns
        -------
        dict
            {courses: [...], total: int}
        """
        if isinstance(course_ids, (list, tuple)):
            course_ids = ",".join(course_ids)
        return self._make_api_call("/api/v1/courses/bulk", params={'ids': course_ids})

    def get_course(self, course_id):
        """
        Full free course detail (tees, holes, climate, nearby, pricing, insights).

        Endpoint: GET /api/v1/courses/{id}

        Parameters
        ----------
        course_id : str

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/courses/{course_id}")

    def get_course_conditions(self, course_id):
        """
        Live conditions at a course (temp/wind/precip from a forecast model, 15-min cache).
        Feeds compute_plays_like().

        Endpoint: GET /api/v1/courses/{id}/conditions

        Parameters
        ----------
        course_id : str

        Returns
        -------
        dict
            conditions{temp_f, wind{speed_mph, direction_deg, gust_mph}, precipitation_in}
        """
        return self._make_api_call(f"/api/v1/courses/{course_id}/conditions")

    def get_course_tees(self, course_id):
        """
        Tee ratings for a course.

        Endpoint: GET /api/v1/courses/{id}/tees

        Parameters
        ----------
        course_id : str

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/courses/{course_id}/tees")

    def get_course_holes(self, course_id):
        """
        Holes with hazards for a course.

        Endpoint: GET /api/v1/courses/{id}/holes

        Parameters
        ----------
        course_id : str

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/courses/{course_id}/holes")

    def get_course_hole(self, course_id, hole_number):
        """
        Single hole detail.

        Endpoint: GET /api/v1/courses/{id}/holes/{num}

        Parameters
        ----------
        course_id : str
        hole_number : int

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/courses/{course_id}/holes/{hole_number}")

    def get_course_weather(self, course_id):
        """
        Live weather forecast for a course (Weather.gov).

        Endpoint: GET /api/v1/courses/{id}/weather

        Parameters
        ----------
        course_id : str

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/courses/{course_id}/weather")

    def get_course_climate(self, course_id):
        """
        Seasonality & best months to play.

        Endpoint: GET /api/v1/courses/{id}/climate

        Parameters
        ----------
        course_id : str

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/courses/{course_id}/climate")

    def get_course_nearby(self, course_id):
        """
        Nearby hotels, restaurants, courses (POIs within ~25mi).

        Endpoint: GET /api/v1/courses/{id}/nearby

        Parameters
        ----------
        course_id : str

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/courses/{course_id}/nearby")

    def get_course_pricing(self, course_id):
        """
        Latest green-fee pricing.

        Endpoint: GET /api/v1/courses/{id}/pricing

        Parameters
        ----------
        course_id : str

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/courses/{course_id}/pricing")

    def get_course_difficulty(self, course_id):
        """
        Difficulty percentile vs nearby courses.

        Endpoint: GET /api/v1/courses/{id}/difficulty

        Parameters
        ----------
        course_id : str

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/courses/{course_id}/difficulty")

    def get_course_daylight(self, course_id, date=None):
        """
        Sunrise/sunset & optimal tee windows.

        Endpoint: GET /api/v1/courses/{id}/daylight

        Parameters
        ----------
        course_id : str
        date : str, optional
            Date in YYYY-MM-DD format, defaults to today (API side).

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/courses/{course_id}/daylight", params={'date': date})

    def create_course(self, course_name, latitude, longitude, holes=None, course_type=None, website=None):
        """
        Create a new (blank-canvas) course from name + GPS. Dedups against existing courses (returns the
        match if found); otherwise queues for human review. Requires API key.

        Endpoint: POST /api/v1/courses

        Parameters
        ----------
        course_name : str
        latitude : float
        longitude : float
        holes : int, optional
        course_type : str, optional
        website : str, optional

        Returns
        -------
        dict
            exists (course_id) | pending (submission_id) | pending_review
        """
        body = self._clean_params({'course_name': course_name, 'latitude': latitude, 'longitude': longitude,
                                   'holes': holes, 'course_type': course_type, 'website': website})
        return self._make_api_call("/api/v1/courses", method="POST", body=body, keyed=True)

    ####################
    # Spatial features (free surface; precise detected layer is gated)
    def get_course_features(self, course_id, hole=None, feature_type=None):
        """
        Course features (greens/bunkers/water polygons). Free = coarse OSM; precise detected layer is gated.

        Endpoint: GET /api/v1/features

        Parameters
        ----------
        course_id : str
        hole : int, optional
        feature_type : str, optional
            e.g. 'green', 'bunker', 'water'

        Returns
        -------
        dict
            GeoJSON features + place_id/sub_unit anchors.
        """
        params = {'course': course_id, 'hole': hole, 'type': feature_type}
        return self._make_api_call("/api/v1/features", params=params)

    def get_nearest_features(self, lat, lng, feature_type=None, limit=None):
        """
        K nearest features to a point (rangefinder step 1).

        Endpoint: GET /api/v1/features/nearest

        Parameters
        ----------
        lat : float
        lng : float
        feature_type : str, optional
        limit : int, optional

        Returns
        -------
        dict
            Features + distance_m.
        """
        params = {'lat': lat, 'lng': lng, 'type': feature_type, 'limit': limit}
        return self._make_api_call("/api/v1/features/nearest", params=params)

    def get_feature_bearing(self, feature_id, lat, lng):
        """
        Compass bearing + distance from a point to a feature (rangefinder step 2).

        Endpoint: GET /api/v1/features/{id}/bearing

        Parameters
        ----------
        feature_id : str
        lat : float
        lng : float

        Returns
        -------
        dict
            bearing_deg + distance_m.
        """
        return self._make_api_call(f"/api/v1/features/{feature_id}/bearing", params={'lat': lat, 'lng': lng})

    def get_containing_features(self, lat, lng, course_id=None):
        """
        Which feature polygons contain a point (geofence / "am I in a bunker").

        Endpoint: GET /api/v1/features/containing

        Parameters
        ----------
        lat : float
        lng : float
        course_id : str, optional

        Returns
        -------
        dict
            Containing features.
        """
        params = {'lat': lat, 'lng': lng, 'course': course_id}
        return self._make_api_call("/api/v1/features/containing", params=params)

    ####################
    # Scoring (OpenMatch - gross scoring is free & keyless)
    def get_scoring_formats(self):
        """
        List scoring formats (engine spec: 16 formats; gross is free).

        Endpoint: GET /api/v1/compute

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/compute")

    def compute_plays_like(self, yards, elevation_delta_ft=None, wind=None, shot_bearing_deg=None,
                           temp_f=None, altitude_ft=None):
        """
        Effective distance ("plays like") - free & keyless. Live wind is available via
        get_course_conditions().

        Endpoint: POST /api/v1/compute/plays_like

        Parameters
        ----------
        yards : float
            Actual distance in yards.
        elevation_delta_ft : float, optional
            Elevation change in feet (positive = uphill).
        wind : dict, optional
            {'speed_mph': float, 'direction_deg': float}
        shot_bearing_deg : float, optional
            Direction of the shot in degrees.
        temp_f : float, optional
        altitude_ft : float, optional

        Returns
        -------
        dict
            {effective_yards, factors[]} - factors itemized.
        """
        body = self._clean_params({'yards': yards, 'elevation_delta_ft': elevation_delta_ft, 'wind': wind,
                                   'shot_bearing_deg': shot_bearing_deg, 'temp_f': temp_f,
                                   'altitude_ft': altitude_ft})
        return self._make_api_call("/api/v1/compute/plays_like", method="POST", body=body)

    def compute_score(self, scoring_format, game_data):
        """
        Score a game (GROSS) - free & keyless. Send gross strokes (net/handicap not accepted here).

        Endpoint: POST /api/v1/compute/{format}

        Parameters
        ----------
        scoring_format : str
            stroke | stableford | match_play | skins | scramble | best_ball | nassau | ctp |
            longest_drive | wolf | ... (see get_scoring_formats()).
        game_data : dict
            players[] + holes[] for stroke formats, or entries[] for shot formats.

        Returns
        -------
        dict
            Standings.
        """
        return self._make_api_call(f"/api/v1/compute/{scoring_format}", method="POST", body=game_data)

    ####################
    # Competitions (contest wrapper over OpenMatch)
    def create_competition(self, name, competition_type, course_id=None, holes=None, format_config=None,
                           org_id=None, starts_at=None, ends_at=None):
        """
        Create a competition. Requires API key.

        Endpoint: POST /api/v1/competitions

        Parameters
        ----------
        name : str
        competition_type : str
            Any OpenMatch format (see get_scoring_formats()).
        course_id : str, optional
        holes : list of int, optional
        format_config : dict, optional
        org_id : str, optional
        starts_at : str, optional
        ends_at : str, optional

        Returns
        -------
        dict
            Competition created.
        """
        body = self._clean_params({'name': name, 'type': competition_type, 'course_id': course_id,
                                   'holes': holes, 'format_config': format_config, 'org_id': org_id,
                                   'starts_at': starts_at, 'ends_at': ends_at})
        return self._make_api_call("/api/v1/competitions", method="POST", body=body, keyed=True)

    def get_competitions(self, org=None, course=None, status=None):
        """
        List competitions.

        Endpoint: GET /api/v1/competitions

        Parameters
        ----------
        org : str, optional
        course : str, optional
        status : str, optional

        Returns
        -------
        dict
        """
        params = {'org': org, 'course': course, 'status': status}
        return self._make_api_call("/api/v1/competitions", params=params)

    def get_competition(self, competition_id):
        """
        Competition metadata + live gross Result (runs the format kernel on demand).

        Endpoint: GET /api/v1/competitions/{id}

        Parameters
        ----------
        competition_id : str

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/competitions/{competition_id}")

    def record_competition_attempt(self, competition_id, attempt):
        """
        Record an Attempt. Requires API key.

        Endpoint: POST /api/v1/competitions/{id}/attempt

        Parameters
        ----------
        competition_id : str
        attempt : dict
            Stroke formats: {player_id, team_id?, hole, strokes, playing_handicap?}.
            Shot formats (ctp/longest_drive/...): {player_id, hole, value, fairway?}.

        Returns
        -------
        dict
            Attempt recorded (409 if competition finalized).
        """
        return self._make_api_call(f"/api/v1/competitions/{competition_id}/attempt", method="POST",
                                   body=attempt, keyed=True)

    def record_selected_ball(self, competition_id, team_id, chosen_player_id, hole, lat=None, lng=None,
                             attested_by=None):
        """
        Record a SelectedBall for scramble. Requires API key.

        Endpoint: POST /api/v1/competitions/{id}/selected-ball

        Parameters
        ----------
        competition_id : str
        team_id : str
        chosen_player_id : str
        hole : int
        lat : float, optional
        lng : float, optional
        attested_by : str, optional

        Returns
        -------
        dict
        """
        body = self._clean_params({'team_id': team_id, 'chosen_player_id': chosen_player_id, 'hole': hole,
                                   'lat': lat, 'lng': lng, 'attested_by': attested_by})
        return self._make_api_call(f"/api/v1/competitions/{competition_id}/selected-ball", method="POST",
                                   body=body, keyed=True)

    def finalize_competition(self, competition_id):
        """
        Finalize a competition -> the free gross Result. Runs the format kernel over all attempts, stores
        the Result, emits competition_finalized. Requires API key.

        Endpoint: POST /api/v1/competitions/{id}/finalize

        Parameters
        ----------
        competition_id : str

        Returns
        -------
        dict
            Result.
        """
        return self._make_api_call(f"/api/v1/competitions/{competition_id}/finalize", method="POST",
                                   keyed=True)

    def supersede_competition_result(self, competition_id, reason=None, result=None):
        """
        Supersede a finalized Result - corrects WITHOUT editing: creates a NEW immutable Result, points
        the old one forward, and moves the current pointer. Requires API key.

        Endpoint: POST /api/v1/competitions/{id}/supersede

        Parameters
        ----------
        competition_id : str
        reason : str, optional
        result : dict, optional

        Returns
        -------
        dict
            superseded_result_id + current_result_id (409 if not finalized).
        """
        body = self._clean_params({'reason': reason, 'result': result})
        return self._make_api_call(f"/api/v1/competitions/{competition_id}/supersede", method="POST",
                                   body=body, keyed=True)

    def get_competition_results(self, competition_id):
        """
        The immutable Result lineage (free) - full oldest->current chain of Results with the current
        pointer.

        Endpoint: GET /api/v1/competitions/{id}/results

        Parameters
        ----------
        competition_id : str

        Returns
        -------
        dict
            current_result_id + results[].
        """
        return self._make_api_call(f"/api/v1/competitions/{competition_id}/results")

    ####################
    # Organizations (public directory, free)
    def get_organizations(self, org_type=None, parent=None):
        """
        Public directory of verified organizations (courses, clubs, sponsors, leagues, charities).

        Endpoint: GET /api/v1/orgs

        Parameters
        ----------
        org_type : str, optional
        parent : str, optional

        Returns
        -------
        dict
        """
        params = {'type': org_type, 'parent': parent}
        return self._make_api_call("/api/v1/orgs", params=params)

    def get_organization(self, org_id):
        """
        A verified org public profile.

        Endpoint: GET /api/v1/orgs/{id}

        Parameters
        ----------
        org_id : str

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/orgs/{org_id}")

    ####################
    # Assets (the mint: trophies, badges, coupons, memberships, collectibles)
    def get_assets(self, owner):
        """
        Trophy case - assets + legacy award trophies, unified.

        Endpoint: GET /api/v1/assets

        Parameters
        ----------
        owner : str
            OpenGolf ID or player_id.

        Returns
        -------
        dict
            Owned assets.
        """
        return self._make_api_call("/api/v1/assets", params={'owner': owner})

    def get_asset(self, asset_id):
        """
        One asset.

        Endpoint: GET /api/v1/assets/{id}

        Parameters
        ----------
        asset_id : str

        Returns
        -------
        dict
        """
        return self._make_api_call(f"/api/v1/assets/{asset_id}")

    def mint_asset(self, owner, name, asset_type=None, description=None, issuer_org=None, image_url=None,
                   metadata=None, idempotency_key=None):
        """
        Mint an Asset to an owner. Requires API key with scope assets:issue.

        Endpoint: POST /api/v1/assets/mint

        Parameters
        ----------
        owner : str
        name : str
        asset_type : str, optional
            trophy | coupon | membership | stamp | collectible | badge
        description : str, optional
        issuer_org : str, optional
        image_url : str, optional
        metadata : dict, optional
        idempotency_key : str, optional
            Sent as Idempotency-Key header for safe retries.

        Returns
        -------
        dict
            Asset minted (403 if missing scope assets:issue).
        """
        body = self._clean_params({'owner': owner, 'name': name, 'type': asset_type,
                                   'description': description, 'issuer_org': issuer_org,
                                   'image_url': image_url, 'metadata': metadata})
        extra_headers = {'Idempotency-Key': idempotency_key} if idempotency_key is not None else None
        return self._make_api_call("/api/v1/assets/mint", method="POST", body=body, keyed=True,
                                   extra_headers=extra_headers)

    def transfer_asset(self, asset_id, to_owner):
        """
        Transfer an asset (lifecycle issued -> transferred). Requires API key with scope assets:issue.

        Endpoint: POST /api/v1/assets/{id}/transfer

        Parameters
        ----------
        asset_id : str
        to_owner : str

        Returns
        -------
        dict
            Transferred (409 on illegal lifecycle transition).
        """
        return self._make_api_call(f"/api/v1/assets/{asset_id}/transfer", method="POST",
                                   body={'to': to_owner}, keyed=True)

    def revoke_asset(self, asset_id):
        """
        Revoke an asset (lifecycle -> revoked). Requires API key with scope assets:issue.

        Endpoint: POST /api/v1/assets/{id}/revoke

        Parameters
        ----------
        asset_id : str

        Returns
        -------
        dict
            Revoked (409 on illegal lifecycle transition).
        """
        return self._make_api_call(f"/api/v1/assets/{asset_id}/revoke", method="POST", keyed=True)

    ####################
    # Auth - Sign in with OpenGolf (OIDC, keyless)
    def send_verify_email(self, email, dry=None):
        """
        Golfer sign-in: email a magic link + 6-digit code (the /id flow).

        Endpoint: POST /oauth/send-verify

        Parameters
        ----------
        email : str
        dry : bool, optional

        Returns
        -------
        dict
        """
        body = self._clean_params({'email': email, 'dry': dry})
        return self._make_api_call("/oauth/send-verify", method="POST", body=body)

    def oauth_start(self, email, client_id):
        """
        Sign in with OpenGolf step 1 - email a 6-digit code. The email IS the OpenGolf ID. No key needed.

        Endpoint: POST /oauth/start

        Parameters
        ----------
        email : str
        client_id : str

        Returns
        -------
        dict
            Code emailed (429 if throttled).
        """
        return self._make_api_call("/oauth/start", method="POST", body={'email': email, 'client_id': client_id})

    def oauth_submit_code(self, email, otp, client_id, redirect_uri, scope=None, code_challenge=None):
        """
        Sign in with OpenGolf step 2 - verify the emailed code -> short-lived auth code (PKCE S256).
        Returns a redirect carrying ?code=.

        Endpoint: POST /oauth/code

        Parameters
        ----------
        email : str
        otp : str
            The 6-digit code from the email.
        client_id : str
        redirect_uri : str
            Must be https.
        scope : str, optional
        code_challenge : str, optional
            PKCE S256 code challenge.

        Returns
        -------
        dict
            Auth code (in redirect). 401 on invalid/expired code.
        """
        body = self._clean_params({'email': email, 'otp': otp, 'client_id': client_id,
                                   'redirect_uri': redirect_uri, 'scope': scope,
                                   'code_challenge': code_challenge})
        return self._make_api_call("/oauth/code", method="POST", body=body)

    def oauth_exchange_token(self, code, redirect_uri, client_id, code_verifier):
        """
        Sign in with OpenGolf step 3 - exchange auth code -> id_token + access_token. Use the
        access_token via set_opengolf_token() for identity endpoints.

        Endpoint: POST /oauth/token

        Parameters
        ----------
        code : str
        redirect_uri : str
        client_id : str
        code_verifier : str
            PKCE code verifier.

        Returns
        -------
        dict
            Tokens.
        """
        body = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri,
                'client_id': client_id, 'code_verifier': code_verifier}
        return self._make_api_call("/oauth/token", method="POST", body=body)

    ####################
    # Developer - identity-backed dev keys (X-OpenGolf-Token required)
    def mint_developer_key(self, email=None):
        """
        Mint a dev key bound to your OpenGolf ID. Sign in first (oauth flow) then set_opengolf_token().
        Key is shown once.

        Endpoint: POST /api/v1/developer/keys

        Parameters
        ----------
        email : str, optional
            The email matching your OpenGolf token.

        Returns
        -------
        dict
            Key issued (shown once).
        """
        body = self._clean_params({'email': email})
        return self._make_api_call("/api/v1/developer/keys", method="POST", body=body if body else None,
                                   token=True)

    def get_developer_keys(self):
        """
        List your keys (prefixes only). Requires X-OpenGolf-Token.

        Endpoint: GET /api/v1/developer/keys

        Returns
        -------
        dict
            Your key prefixes.
        """
        return self._make_api_call("/api/v1/developer/keys", token=True)

    def link_developer_key(self):
        """
        Confirm your OpenGolf ID on an existing (legacy) key. Requires both the API key and
        X-OpenGolf-Token; verifies + keeps the key and its scopes.

        Endpoint: POST /api/v1/developer/keys/link

        Returns
        -------
        dict
            Linked.
        """
        return self._make_api_call("/api/v1/developer/keys/link", method="POST", keyed=True, token=True)

    def register_developer_app(self, name, app_type=None, redirect_uris=None):
        """
        Register an app/entity under your OpenGolf ID. The registered app is the Organization primitive -
        it gets a trusted name+logo on the sign-in consent screen once verified. Requires X-OpenGolf-Token.

        Endpoint: POST /api/v1/developer/apps

        Parameters
        ----------
        name : str
        app_type : str, optional
            app | company | course | organizer
        redirect_uris : list of str, optional

        Returns
        -------
        dict
            App registered.
        """
        body = self._clean_params({'name': name, 'type': app_type, 'redirect_uris': redirect_uris})
        return self._make_api_call("/api/v1/developer/apps", method="POST", body=body, token=True)

    def get_developer_apps(self):
        """
        List your registered apps/entities. Requires X-OpenGolf-Token.

        Endpoint: GET /api/v1/developer/apps

        Returns
        -------
        dict
            Your apps.
        """
        return self._make_api_call("/api/v1/developer/apps", token=True)

    ####################
    # Identity / join (foursome & league invites, profiles)
    def mint_join_token(self, session_id=None, event_id=None, max_uses=None, expires_in=None):
        """
        Mint a signed, expiring group-join token (foursome/league invite; max_uses caps size).
        Requires API key.

        Endpoint: POST /api/v1/join/mint

        Parameters
        ----------
        session_id : str, optional
        event_id : str, optional
        max_uses : int, optional
        expires_in : int, optional
            Seconds until the token expires.

        Returns
        -------
        dict
            {token, url, qr}
        """
        body = self._clean_params({'session_id': session_id, 'event_id': event_id, 'max_uses': max_uses,
                                   'expires_in': expires_in})
        return self._make_api_call("/api/v1/join/mint", method="POST", body=body, keyed=True)

    def redeem_join_token(self, token, player=None):
        """
        Redeem a join token - links the redeemer into the session/event.

        Endpoint: POST /api/v1/join/redeem

        Parameters
        ----------
        token : str
        player : dict, optional

        Returns
        -------
        dict
            Joined (410 if expired/used up).
        """
        body = self._clean_params({'token': token, 'player': player})
        return self._make_api_call("/api/v1/join/redeem", method="POST", body=body)

    def join_login(self, email=None, code=None, ref=None):
        """
        Sign in with OpenGolf (hosted): start/complete the verified-code flow.

        Endpoint: POST /api/v1/join/login

        Parameters
        ----------
        email : str, optional
        code : str, optional
        ref : str, optional

        Returns
        -------
        dict
            Session token / code sent.
        """
        body = self._clean_params({'email': email, 'code': code, 'ref': ref})
        return self._make_api_call("/api/v1/join/login", method="POST", body=body)

    def get_profile(self, profile_id):
        """
        Read a profile (keyed - identity-scoped). Requires API key.

        Endpoint: GET /api/v1/join/profile/{id}

        Parameters
        ----------
        profile_id : str

        Returns
        -------
        dict
            Profile.
        """
        return self._make_api_call(f"/api/v1/join/profile/{profile_id}", keyed=True)

    def update_profile(self, profile_data):
        """
        Edit YOUR profile (name/avatar/links; handicap is engine-derived, not editable). Requires API key.

        Endpoint: PATCH /api/v1/join/profile

        Parameters
        ----------
        profile_data : dict

        Returns
        -------
        dict
            Updated.
        """
        return self._make_api_call("/api/v1/join/profile", method="PATCH", body=profile_data, keyed=True)

    ####################
    # Presence beacons (opt-in "I am at the course")
    def set_presence_beacon(self, beacon_data):
        """
        Set a presence beacon (opt-in "I am at the course"). Requires API key.

        Endpoint: POST /api/v1/join/beacon

        Parameters
        ----------
        beacon_data : dict

        Returns
        -------
        dict
            Beacon set.
        """
        return self._make_api_call("/api/v1/join/beacon", method="POST", body=beacon_data, keyed=True)

    def get_presence_beacons(self, query_params=None):
        """
        Find active beacons near a course (consented presence only).

        Endpoint: GET /api/v1/join/beacons

        Parameters
        ----------
        query_params : dict, optional
            Query filters (e.g., {'course': course_id}).

        Returns
        -------
        dict
            Beacons.
        """
        return self._make_api_call("/api/v1/join/beacons", params=query_params)

    ####################
    # Sessions (rounds)
    def get_session_scorecard(self, session_id):
        """
        Fold a session's score moments into a scorecard (participant or compute-entitled).

        Endpoint: GET /api/v1/sessions/{id}/scorecard

        Parameters
        ----------
        session_id : str

        Returns
        -------
        dict
            Scorecard.
        """
        return self._make_api_call(f"/api/v1/sessions/{session_id}/scorecard")

    def get_session_leaderboard(self, session_id, score_format=None):
        """
        Gross or net leaderboard for a session.

        Endpoint: GET /api/v1/sessions/{id}/leaderboard

        Parameters
        ----------
        session_id : str
        score_format : str, optional
            'gross' or 'net'.

        Returns
        -------
        dict
            Leaderboard.
        """
        return self._make_api_call(f"/api/v1/sessions/{session_id}/leaderboard",
                                   params={'format': score_format})

    def get_session_live_state(self, session_id, include=None):
        """
        live_state - composed realtime view of a session.

        Endpoint: GET /api/v1/sessions/{id}/synthesize

        Parameters
        ----------
        session_id : str
        include : str or list, optional
            Comma-separated string or list from: leaderboard, sidegames, presence, pace, highlights.

        Returns
        -------
        dict
            Composed live state.
        """
        if isinstance(include, (list, tuple)):
            include = ",".join(include)
        return self._make_api_call(f"/api/v1/sessions/{session_id}/synthesize", params={'include': include})

    def get_session_feed(self, session_id, since=None, kinds=None, limit=None):
        """
        OpenBroadcast feed - one typed read: broadcast-worthy items, ascending (recorded_at, seq),
        template narration, money only when settled.

        Endpoint: GET /api/v1/sessions/{id}/feed

        Parameters
        ----------
        session_id : str
        since : str, optional
            Cursor from a previous call (next_since).
        kinds : str, optional
            Filter to specific broadcast kinds.
        limit : int, optional

        Returns
        -------
        dict
            Feed items + next_since cursor.
        """
        params = {'since': since, 'kinds': kinds, 'limit': limit}
        return self._make_api_call(f"/api/v1/sessions/{session_id}/feed", params=params)

    ####################
    # Events (multi-round tournaments)
    def create_event(self, event_config):
        """
        Create an OpenEvent - multi-round tournament (parent of N sessions). Requires API key.

        Endpoint: POST /api/v1/events

        Parameters
        ----------
        event_config : dict

        Returns
        -------
        dict
            Event.
        """
        return self._make_api_call("/api/v1/events", method="POST", body=event_config, keyed=True)

    def get_event(self, event_id):
        """
        Event config + status.

        Endpoint: GET /api/v1/events/{id}

        Parameters
        ----------
        event_id : str

        Returns
        -------
        dict
            Event.
        """
        return self._make_api_call(f"/api/v1/events/{event_id}")

    def get_event_leaderboard(self, event_id):
        """
        Rolled gross+net leaderboard across all rounds, by division.

        Endpoint: GET /api/v1/events/{id}/leaderboard

        Parameters
        ----------
        event_id : str

        Returns
        -------
        dict
            Leaderboard.
        """
        return self._make_api_call(f"/api/v1/events/{event_id}/leaderboard")

    ####################
    # Players & awards
    def get_player_awards(self, player_id):
        """
        A player's trophy case (derived + organizer awards + course passport).

        Endpoint: GET /api/v1/awards/players/{id}

        Parameters
        ----------
        player_id : str
            OpenGolf ID (ogid_...).

        Returns
        -------
        dict
            Awards.
        """
        return self._make_api_call(f"/api/v1/awards/players/{player_id}")

    def get_player_handicap(self, player_id):
        """
        OpenIndex (beta) - estimated handicap from notarized rounds (self-sovereign: your own is free).

        Endpoint: GET /api/v1/players/{id}/handicap

        Parameters
        ----------
        player_id : str

        Returns
        -------
        dict
            Handicap + provisional flags.
        """
        return self._make_api_call(f"/api/v1/players/{player_id}/handicap")

    ####################
    # Webhooks
    def register_webhook(self, url, events=None, secret=None, filters=None):
        """
        Register an https endpoint for your domain events (HMAC-signed: X-OG-Signature = hex sha256 of
        raw body). Requires API key.

        Endpoint: POST /api/v1/webhooks

        Parameters
        ----------
        url : str
            Your https endpoint.
        events : list of str, optional
        secret : str, optional
        filters : dict, optional

        Returns
        -------
        dict
            Subscription.
        """
        body = self._clean_params({'url': url, 'events': events, 'secret': secret, 'filters': filters})
        return self._make_api_call("/api/v1/webhooks", method="POST", body=body, keyed=True)

    def get_webhooks(self):
        """
        List your active webhook subscriptions. Requires API key.

        Endpoint: GET /api/v1/webhooks

        Returns
        -------
        dict
            Subscriptions.
        """
        return self._make_api_call("/api/v1/webhooks", keyed=True)

    def delete_webhook(self, webhook_id):
        """
        Deactivate a webhook subscription (audit row kept). Requires API key.

        Endpoint: DELETE /api/v1/webhooks/{id}

        Parameters
        ----------
        webhook_id : str

        Returns
        -------
        dict
            Deactivated.
        """
        return self._make_api_call(f"/api/v1/webhooks/{webhook_id}", method="DELETE", keyed=True)

    def replay_stream(self, query_params=None):
        """
        Replay your domain events after a cursor (owner-scoped; seq cursor). Requires API key.

        Endpoint: GET /api/v1/stream/replay

        Parameters
        ----------
        query_params : dict, optional
            Cursor/filter params, e.g. {'since': <seq>}.

        Returns
        -------
        dict
            Events.
        """
        return self._make_api_call("/api/v1/stream/replay", params=query_params, keyed=True)

    ####################
    # Contribute - shots (OpenShot standard, requires API key unless noted)
    def post_shots(self, shots):
        """
        Ingest launch-monitor shots - one shot or an array (max 500). OpenShot or raw GSPro OpenConnect
        JSON. Idempotent via dedup_key. Requires API key. See get_openshot_fields() for the field catalog.

        Endpoint: POST /api/v1/shots

        Parameters
        ----------
        shots : dict or list of dict
            Shot(s) with at minimum {api_version, ball: {speed}}.

        Returns
        -------
        dict
            {ok, ingested, ids}
        """
        return self._make_api_call("/api/v1/shots", method="POST", body=shots, keyed=True)

    def get_shots(self, player=None, session=None, limit=None):
        """
        Read your own shot history. Requires API key.

        Endpoint: GET /api/v1/shots

        Parameters
        ----------
        player : str, optional
        session : str, optional
        limit : int, optional

        Returns
        -------
        dict
            Your shots.
        """
        params = {'player': player, 'session': session, 'limit': limit}
        return self._make_api_call("/api/v1/shots", params=params, keyed=True)

    def echo_shot(self, shot):
        """
        Validate/normalize a shot without storing (sandbox) - free & keyless.

        Endpoint: POST /api/v1/shots/echo

        Parameters
        ----------
        shot : dict

        Returns
        -------
        dict
            Normalized echo (not stored).
        """
        return self._make_api_call("/api/v1/shots/echo", method="POST", body=shot)

    ####################
    # Contribute - moments (any sensor -> one event, requires API key)
    def post_moments(self, moments):
        """
        Ingest Open Connect events (shot | breadcrumb | pin | condition | tee | green | swing | presence
        | ...). One or an array (max 500). Idempotent via dedup_key. Requires API key. See
        get_moments_fields() for payload fields per moment_type.

        Endpoint: POST /api/v1/moments

        Parameters
        ----------
        moments : dict or list of dict
            Moment(s) with at minimum {moment_type}.

        Returns
        -------
        dict
            {ok, ingested, ids}
        """
        return self._make_api_call("/api/v1/moments", method="POST", body=moments, keyed=True)

    def get_moments(self, player=None, session=None, moment_type=None, limit=None):
        """
        Read your own moments. Requires API key.

        Endpoint: GET /api/v1/moments

        Parameters
        ----------
        player : str, optional
        session : str, optional
        moment_type : str, optional
        limit : int, optional

        Returns
        -------
        dict
            Your moments.
        """
        params = {'player': player, 'session': session, 'type': moment_type, 'limit': limit}
        return self._make_api_call("/api/v1/moments", params=params, keyed=True)

    def import_round(self, data, data_format='gpx', player=None, course=None, session=None):
        """
        Import a round export (GPX/CSV/JSON) -> moments. Bridge for existing apps; normalized to
        breadcrumb moments, idempotent (dedup). Backfill your whole history safely. Requires API key.

        Endpoint: POST /api/v1/import

        Parameters
        ----------
        data : str or dict
            The export content. String for gpx/csv; dict (or string) for json.
        data_format : str, optional
            'gpx', 'csv', or 'json', by default 'gpx'.
        player : str, optional
        course : str, optional
        session : str, optional

        Returns
        -------
        dict
            Imported (ok, points, imported, session_id).
        """
        params = {'format': data_format, 'player': player, 'course': course, 'session': session}
        content_types = {'gpx': 'application/gpx+xml', 'csv': 'text/csv', 'json': 'application/json'}
        if data_format == 'json' and not isinstance(data, str):
            return self._make_api_call("/api/v1/import", method="POST", params=params, body=data,
                                       keyed=True)
        return self._make_api_call("/api/v1/import", method="POST", params=params, raw_body=data,
                                   content_type=content_types.get(data_format, 'application/json'),
                                   keyed=True)

    ####################
    # Contribute - corrections (propose fixes to course facts, requires API key)
    def propose_correction(self, course_id, field, proposed_value, evidence_url=None, note=None):
        """
        Propose a correction to a course FACT field (phone, website, address, architect, year_built,
        course_name, city, postal_code, course_type). AI-reviewed; approved+confident fixes apply.
        Geometry is not correctable. Requires API key.

        Endpoint: POST /api/v1/corrections

        Parameters
        ----------
        course_id : str
        field : str
        proposed_value : str
        evidence_url : str, optional
        note : str, optional

        Returns
        -------
        dict
            Submitted (correction_id, status).
        """
        body = self._clean_params({'course_id': course_id, 'field': field, 'proposed_value': proposed_value,
                                   'evidence_url': evidence_url, 'note': note})
        return self._make_api_call("/api/v1/corrections", method="POST", body=body, keyed=True)

    def get_correction(self, correction_id):
        """
        Check a correction's status/verdict. Requires API key.

        Endpoint: GET /api/v1/corrections/{id}

        Parameters
        ----------
        correction_id : str

        Returns
        -------
        dict
            status: pending | applied | rejected | needs_info | human
        """
        return self._make_api_call(f"/api/v1/corrections/{correction_id}", keyed=True)

    def respond_to_correction(self, correction_id, note=None, evidence_url=None):
        """
        Answer a needs_info correction (add a source) -> re-review. Requires API key.

        Endpoint: POST /api/v1/corrections/{id}/respond

        Parameters
        ----------
        correction_id : str
        note : str, optional
        evidence_url : str, optional

        Returns
        -------
        dict
            Re-opened for review.
        """
        body = self._clean_params({'note': note, 'evidence_url': evidence_url})
        return self._make_api_call(f"/api/v1/corrections/{correction_id}/respond", method="POST",
                                   body=body, keyed=True)

    ####################
    # Contribute - your data (GDPR/CCPA export & delete, requires API key)
    def get_my_data(self, player=None):
        """
        Export your own contributed data (moments + shots). Requires API key.

        Endpoint: GET /api/v1/me

        Parameters
        ----------
        player : str, optional

        Returns
        -------
        dict
            Your moments + shots.
        """
        return self._make_api_call("/api/v1/me", params={'player': player}, keyed=True)

    def delete_my_data(self, player=None):
        """
        Delete your own contributed data (GDPR/CCPA). Requires API key.

        Endpoint: DELETE /api/v1/me

        Parameters
        ----------
        player : str, optional

        Returns
        -------
        dict
            Deleted counts.
        """
        return self._make_api_call("/api/v1/me", method="DELETE", params={'player': player}, keyed=True)

    ####################
    # Chain (verifiable self-sovereign records; own-reads require API key, public reads keyless)
    def get_my_chain(self):
        """
        Export your OpenGolf Chain (verifiable self-sovereign record) - your append-only, tamper-evident
        hash chain over your own moment stream, plus its signed + OpenTimestamps-anchored checkpoints.
        Requires API key.

        Endpoint: GET /api/v1/me/chain

        Returns
        -------
        dict
            subject, length, head, entries[], checkpoints[]
        """
        return self._make_api_call("/api/v1/me/chain", keyed=True)

    def checkpoint_my_chain(self):
        """
        Checkpoint your chain (sign + stage OpenTimestamps anchor) - materializes your chain,
        Merkle-roots it, RS256-signs the digest, and stages it for Bitcoin anchoring. Requires API key.

        Endpoint: POST /api/v1/me/chain/checkpoint

        Returns
        -------
        dict
            The stored checkpoint.
        """
        return self._make_api_call("/api/v1/me/chain/checkpoint", method="POST", keyed=True)

    def verify_chain_export(self, chain_export):
        """
        Verify a chain export (public tool, no key) - stateless: recomputes an export's links and
        optionally its checkpoint signature and Merkle root.

        Endpoint: POST /api/v1/me/chain/verify

        Parameters
        ----------
        chain_export : dict
            A chain export (e.g., from get_my_chain()).

        Returns
        -------
        dict
            chain verdict + signature_valid + merkle_root_matches
        """
        return self._make_api_call("/api/v1/me/chain/verify", method="POST", body=chain_export)

    def get_chain_anchor(self, anchor_id):
        """
        Resolve a record's anchor -> its checkpoint + Bitcoin proof. Keyless.

        Endpoint: GET /api/v1/chain/anchors/{id}

        Parameters
        ----------
        anchor_id : str
            A checkpoint id (a record's anchor_ref).

        Returns
        -------
        dict
            checkpoint + sig + Bitcoin proof (+ rollup)
        """
        return self._make_api_call(f"/api/v1/chain/anchors/{anchor_id}")

    def get_chain_inclusion_proof(self, anchor_id, content_hash):
        """
        Merkle inclusion proof: a record is under the anchored root. Offline-verifiable. Keyless.

        Endpoint: GET /api/v1/chain/anchors/{id}/inclusion

        Parameters
        ----------
        anchor_id : str
        content_hash : str
            The content_hash to prove inclusion for.

        Returns
        -------
        dict
            leaf, index, proof[], merkle_root, root_matches
        """
        return self._make_api_call(f"/api/v1/chain/anchors/{anchor_id}/inclusion",
                                   params={'hash': content_hash})

    def get_chain_log(self, subject=None, since_seq=None, limit=None):
        """
        The public append-only transparency log - walk the whole chain for a subject (og:registry,
        og:course:<id>, og:root). Keyless.

        Endpoint: GET /api/v1/chain/log

        Parameters
        ----------
        subject : str, optional
        since_seq : int, optional
        limit : int, optional

        Returns
        -------
        dict
            subject, checkpoints[], next_since
        """
        params = {'subject': subject, 'since_seq': since_seq, 'limit': limit}
        return self._make_api_call("/api/v1/chain/log", params=params)

    ####################
    # Claims (trust ledger; reads free, writes require API key)
    def get_claims(self, claimant=None, subject=None, status=None):
        """
        List claims (trust ledger). Reads are free.

        Endpoint: GET /api/v1/claims

        Parameters
        ----------
        claimant : str, optional
        subject : str, optional
        status : str, optional

        Returns
        -------
        dict
            claims[]
        """
        params = {'claimant': claimant, 'subject': subject, 'status': status}
        return self._make_api_call("/api/v1/claims", params=params)

    def file_claim(self, claim_data):
        """
        File a claim - open a verifiable assertion (ownership/attestation/identity/record). Lifecycle
        open -> accepted -> disputed -> verified. Requires API key.

        Endpoint: POST /api/v1/claims

        Parameters
        ----------
        claim_data : dict

        Returns
        -------
        dict
            The created claim.
        """
        return self._make_api_call("/api/v1/claims", method="POST", body=claim_data, keyed=True)

    def get_claim(self, claim_id):
        """
        A claim + its evidence. Reads are free.

        Endpoint: GET /api/v1/claims/{id}

        Parameters
        ----------
        claim_id : str

        Returns
        -------
        dict
            claim + evidence[]
        """
        return self._make_api_call(f"/api/v1/claims/{claim_id}")

    def attach_claim_evidence(self, claim_id, evidence_data):
        """
        Attach evidence to a claim. Requires API key.

        Endpoint: POST /api/v1/claims/{id}/evidence

        Parameters
        ----------
        claim_id : str
        evidence_data : dict

        Returns
        -------
        dict
            The created evidence.
        """
        return self._make_api_call(f"/api/v1/claims/{claim_id}/evidence", method="POST",
                                   body=evidence_data, keyed=True)

    ####################
    # Entitlements
    def get_entitlements(self, subject=None):
        """
        List your entitlements - the access grants attached to your OpenGolf ID. Reading your own is
        free but requires API key.

        Endpoint: GET /api/v1/entitlements

        Parameters
        ----------
        subject : str, optional

        Returns
        -------
        dict
            subject + entitlements[]
        """
        return self._make_api_call("/api/v1/entitlements", params={'subject': subject}, keyed=True)

    ####################
    # Beta (local course knowledge; reads free, writes require API key)
    def get_course_beta(self, course_id, hole=None):
        """
        Raw local course knowledge ("beta") for a course/hole - the AI-caddie's fuel. Raw reads are free.

        Endpoint: GET /api/v1/beta

        Parameters
        ----------
        course_id : str
        hole : int, optional

        Returns
        -------
        dict
            beta[]
        """
        return self._make_api_call("/api/v1/beta", params={'course': course_id, 'hole': hole})

    def post_course_beta(self, beta_data):
        """
        Drop local knowledge ("beta") for a course/hole. Requires API key.

        Endpoint: POST /api/v1/beta

        Parameters
        ----------
        beta_data : dict

        Returns
        -------
        dict
            The recorded beta.
        """
        return self._make_api_call("/api/v1/beta", method="POST", body=beta_data, keyed=True)

    ####################
    # Telemetry
    def post_connector_telemetry(self, telemetry_data):
        """
        Connector diagnostics (anonymous OK) - crash/usage reports from Open Connect connectors.

        Endpoint: POST /api/v1/connect/telemetry

        Parameters
        ----------
        telemetry_data : dict

        Returns
        -------
        dict
        """
        return self._make_api_call("/api/v1/connect/telemetry", method="POST", body=telemetry_data)
