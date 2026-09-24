class EventBus:
    """A simple Pub/Sub Event Broker for decoupling UI and hardware logic."""
    _subscribers = {}
    
    @classmethod
    def subscribe(cls, event_type, callback):
        if event_type not in cls._subscribers:
            cls._subscribers[event_type] = []
        cls._subscribers[event_type].append(callback)
        
    @classmethod
    def publish(cls, event_type, **kwargs):
        if event_type in cls._subscribers:
            for callback in cls._subscribers[event_type]:
                callback(**kwargs)
