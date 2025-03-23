from lukhed_basic_utils import fileCommon as fC
from lukhed_basic_utils import osCommon as osC
from lukhed_basic_utils import listWorkCommon as lC
from lukhed_basic_utils import requestsCommon as rC
from lukhed_basic_utils import githubCommon as gC
from lukhed_basic_utils import stringCommon as sC
from lukhed_basic_utils import timeCommon as tC


class TeamConversion:
    def __init__(self, sport, use_cache=True, reset_cache=False):
        """
        This class is used to convert team names between different data providers.

        Parameters
        ----------
        sport : str
            The sport for which you want to convert team names. Currently only 'nfl' is supported.
        use_cache : bool, optional
            Used to determine if the class should use the cache for the translations, by default True. If False, 
            the class will always pull the data from the cloud.
        reset_cache : bool, optional
            Used to determine if the class should reset the cache for the translations, by default False. If True, 
            the class will delete the cache for the sport and re-download the files from the cloud.
        """

        # Check Instantiation Parameters
        self.sport = sport.lower()
        self._supported_sports = ['nfl']
        self._check_sport_support()
        self.use_cache = use_cache
        self._translations_dir = osC.create_file_path_string(["lukhed_sports", "local_cache", "translations"])
        self.cache_dir = osC.create_file_path_string(["lukhed_sports", "local_cache", "translations", self.sport])

        # Cache logic
        if reset_cache:
            self._delete_cache()
            self._check_create_dir_structure()
            self._download_sport_files_from_cloud()

        if use_cache:
            self._check_create_dir_structure()

        # When there are team name changes, this needs to be maintained in _get_key_for_season
        self.from_season_key = ""
        self.to_season_key = ""

        # This data is used once conversions start. The class will hold the data here to prevent need to re-open files
        self.supported_providers = []
        self.provider_key = {}
        self.season_key = {}
        self.from_data = {}
        self.to_data = {}
        self.current_from_provider = ""
        self.from_list = []
        self.current_to_provider = ""
        self.to_list = []

    def _check_sport_support(self):
        if self.sport not in self._supported_sports:
            print(f"ERROR: sport '{self.sport}' is not supported for team conversions. Request it here: "
                  f"https://github.com/lukhed/lukhed_sports/issues\n\nSupported sports: {self._supported_sports}")

            quit()

    def _download_sport_files_from_cloud(self):
        dir_structure = gC.get_github_json("lukhed", "lukhed_sports_league_data", "translations/structure.json")
        sport_files = dir_structure[self.sport]
        total_files = len(sport_files)
        print(f"Downloading {total_files} files to cache...")
        for i, file in enumerate(sport_files):
            file_content = gC.get_github_json("lukhed", 
                                              "lukhed_sports_league_data", 
                                              f'translations/{self.sport}/{file}')
            fC.dump_json_to_file(osC.append_to_dir(self.cache_dir, file), file_content)
            i = i + 1
            print(f"Downloaded {i} of {total_files} files...")
            tC.sleep(1)

    def _get_file_content(self, fn):
        if self.use_cache:
            cache_file = osC.append_to_dir(self.cache_dir, fn)
            if osC.check_if_file_exists(cache_file):
                return fC.load_json_from_file(cache_file)
            else:
                return self._download_single_file_to_cache(fn)
        else:
            return self._retrieve_single_file_from_cloud(fn)
    
    def _download_single_file_to_cache(self, file_name):
        file_content = gC.get_github_json("lukhed", 
                                          "lukhed_sports_league_data", 
                                          f'translations/{self.sport}/{file_name}')
        fC.dump_json_to_file(osC.append_to_dir(self.cache_dir, file_name), file_content)
        return file_content
    
    def _retrieve_single_file_from_cloud(self, file_name):
        file_content = gC.get_github_json("lukhed", 
                                          "lukhed_sports_league_data", 
                                          f'translations/{self.sport}/{file_name}')
        return file_content
    
    def _check_create_dir_structure(self):
        osC.check_create_dir_structure(self._translations_dir, full_path=True)
        osC.check_create_dir_structure(self.cache_dir, full_path=True)

    def _delete_cache(self):
        if osC.check_if_dir_exists(self.cache_dir):
            print("Deleting cache...")
            osC.delete_directory_with_contents(self.cache_dir)
            tC.sleep(2)

    def _check_get_provider_key(self):
        """
        This gets the file providerKey.json from github or local directory and sets the self.provider_key variable.
        :return:
        """

        fn = "providerKey.json"
        self.provider_key = self._get_file_content(fn)

    def _get_provider_file_content(self, provider):
        """
        This function gets the content of the provider file from the cloud or cache.

        Parameters
        ----------
        provider : str
            The provider for which you want to get the content.

        Returns
        -------
        dict
            The content of the provider file.
        """
        fn = self._get_provider_file_name(provider)
        return self._get_file_content(fn)

    def _get_key_for_season(self, season, provider):
        
        fn = "seasonKey.json"
        if self.season_key == {}:
            self.season_key = self._get_file_content(fn)

        provider_season_key = self.season_key[provider]
        if season == "latest":
            season = max([int(x) for x in provider_season_key])
        else:
            season = int(season)

        for key in provider_season_key:
            temp_list = provider_season_key[key]
            if season in temp_list:
                return key

        # did not find the season in the data
        print("ERROR: The season " + str(season) + " was not found in the season key for " + provider + ". "
              "Generally, the season parameter should only be used for prior season data, If you are looking for "
              "the latest season, use 'latest' as the season parameter.")
        return None
        
    def _set_conversion_lists(self, from_team_type, to_team_type):
        self.from_list = self.from_data[self.from_season_key][from_team_type]
        self.to_list = self.to_data[self.to_season_key][to_team_type]

    def _get_provider_file_name(self, provider_input, check_exist=False):
        """
        Gets the file name from the providerKey file based on the provider input

        Parameters
        ----------
        provider_input : _type_
            _description_
        check_exist : bool, optional
            _description_, by default False

        Returns
        -------
        _type_
            _description_
        """
        provider_input = provider_input.lower()
        self._check_get_provider_key()

        fn = None
        for key in self.provider_key:
            temp_fn = key
            synonyms = [x.lower() for x in self.provider_key[temp_fn]]
            if provider_input in synonyms:
                fn = key
                break

        if fn is not None:
            return fn
        else:
            if check_exist:
                return None
            else:
                print("ERROR: provider cannot be found for the provided input = " + provider_input)
                return fn

    def _set_provider_data(self, provider_input, to_from):
        """
        This function sets the data in the data variables, both raw data in lists for conversions.
        :param provider_input:
        :param to_from:
        :return:
        """
        fn = self._get_provider_file_name(provider_input)

        if to_from == "to":
            if self.current_to_provider == fn:
                return None
        elif to_from == "from":
            if self.current_from_provider == fn:
                return None
        else:
            return None

        data = self._get_file_content(fn)

        if to_from == "to":
            self.to_data = data.copy()
            self.current_to_provider = fn
        elif to_from == "from":
            self.from_data = data.copy()
            self.current_from_provider = fn

        return None

    def convert_team(self, team, from_provider, to_provider, from_team_type="long", to_team_type="long",
                     from_season="latest", to_season="latest"):

        self._set_provider_data(from_provider.lower(), "from")
        self._set_provider_data(to_provider.lower(), "to")

        self.from_season_key = self._get_key_for_season(str(from_season).lower(), self.current_from_provider)
        self.to_season_key = self._get_key_for_season(str(to_season).lower(), self.current_to_provider)

        self._set_conversion_lists(from_team_type, to_team_type)

        # Do the conversion
        temp_team = team.lower()
        temp_from = [x.lower() for x in self.from_list]

        try:
            found_index = temp_from.index(temp_team)
        except ValueError:
            print("WARNING: " + team + " could not be translated as it was not found in the specified from list. "
                                       "Returning back the team.")
            return team

        return self.to_list[found_index]

        """

        :param provider:
        :param year_to_add:
        :param key_to_update:
        :return:
        """

        if self.use_cloud is False:
            print("ERROR: Need cloud on to adjust the season key file")
            quit()

        provider = self._get_provider_file_name(provider)['fn']
        if provider is None:
            print("ERROR: Provider wasn't found. Make sure the provider is in the file before trying to add a "
                  "compatible year")
            quit()

        cloud_fp = self.cloud_base_dir + "seasonKey.json"
        self.season_key = gC.retrieve_json_content_from_file("grindsunday", "grindSports", cloud_fp,
                                                             github_object=self.gh_object)
        current_year_list = self.season_key[provider][str(key_to_update)]
        if int(year_to_add) in current_year_list:
            print("ERROR: the year " + str(year_to_add) + " is already in the season key for " + provider)
            quit()
        else:
            current_year_list.append(int(year_to_add))
            current_year_list.sort()
            gC.update_file_in_repository("grindsunday", "grindSports", cloud_fp, self.season_key,
                                         github_object=self.gh_object)
            print("Added the year successfully...")


        if self.use_cloud is False:
            print("ERROR: Need cloud on to adjust the season key file")
            quit()

        provider = self._get_provider_file_name(provider)['fn']
        if provider is None:
            print("ERROR: Provider wasn't found. Make sure the provider is in the file before trying to add "
                  "synonyms")
            quit()

        cloud_fp = self.cloud_base_dir + "providerKey.json"
        self.provider_key = gC.retrieve_json_content_from_file("grindsunday", "grindSports", cloud_fp,
                                                               github_object=self.gh_object)

        current_synonyms = self.provider_key[provider]

        if type(synonyms_to_add) == str:
            synonyms_to_add = [synonyms_to_add]

        for synonym in synonyms_to_add:
            if synonym.lower() in current_synonyms:
                print(synonym + " is already in the provider synonym list")
            else:
                current_synonyms.append(synonym)
                print(synonym + " was added to the list")

        gC.update_file_in_repository("grindsunday", "grindSports", cloud_fp, self.provider_key,
                                     github_object=self.gh_object)

    def get_team_list(self, provider, team_type, season="latest"):
        """
        Use this function to get a list of teams for a given sport, year, and data provider

        :param season:
        :param provider:
        :param team_type:
        :return:
        """

        self._set_provider_data(provider.lower(), "from")
        file_details = self._get_provider_file_name(provider, check_exist=True)
        season_key = self._get_key_for_season(str(season).lower(), file_details['fn'])
        return self.from_data[season_key][team_type]

    def get_supported_providers(self):
        if self.supported_providers != []:
            return self.supported_providers
        
        fn = "supportedProviders.json"
        data = self._get_file_content(fn)
        self.supported_providers = data['names']

        return self.supported_providers

    def get_supported_data_for_provider(self, provider):
        """
        Returns the supported data for the given provider which contains the years and the team types it supports.
        :param provider:
        :return:
        """

        provider_data = self._get_provider_file_content(provider)
        data_support = []

        for year in provider_data:
            temp_dict = {year: [x for x in provider_data[year]]}
            data_support.append(temp_dict.copy())

        return data_support



