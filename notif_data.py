class NotificationData:
    """Class to store notification data."""

    def __init__(self):
        """
        Initialize NotificationData with default values.
        Attributes:
            _entity: Entity information.
            _category: Category information.
            _subcategory: Subcategory information.
            _motive: Motive information.
            _district: District information.
            _local: Local information.
            _service_desk: Service desk information.
        """
        self._entity = None
        self._category = None
        self._subcategory = None
        self._motive = None
        self._district = None
        self._local = None
        self._service_desk = None

    # Getter methods
    def get_entity(self):
        """Get entity information."""
        return self._entity

    def get_category(self):
        """Get category information."""
        return self._category

    def get_subcategory(self):
        """Get subcategory information."""
        return self._subcategory

    def get_motive(self):
        """Get motive information."""
        return self._motive

    def get_district(self):
        """Get district information."""
        return self._district

    def get_local(self):
        """Get local information."""
        return self._local

    def get_service_desk(self):
        """Get service desk information."""
        return self._service_desk

    # Setter methods
    def set_entity(self, entity):
        """
        Set entity information.
        Args:
            entity: Entity information to set.
        """
        self._entity = entity

    def set_category(self, category):
        """
        Set category information.
        Args:
            category: Category information to set.
        """
        self._category = category

    def set_subcategory(self, subcategory):
        """
        Set subcategory information.
        Args:
            subcategory: Subcategory information to set.
        """
        self._subcategory = subcategory

    def set_motive(self, motive):
        """
        Set motive information.
        Args:
            motive: Motive information to set.
        """
        self._motive = motive

    def set_district(self, district):
        """
        Set district information.
        Args:
            district: District information to set.
        """
        self._district = district

    def set_local(self, local):
        """
        Set local information.
        Args:
            local: Local information to set.
        """
        self._local = local

    def set_service_desk(self, service_desk):
        """
        Set service desk information.
        Args:
            service_desk: Service desk information to set.
        """
        self._service_desk = service_desk
