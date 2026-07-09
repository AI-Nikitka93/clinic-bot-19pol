import asyncio
import json
from app.scraper.differ import diff_state

def test_differ():
    old_state = {
        "Dentist": {
            "doctors": {
                "Dr. Smith": {"tickets": {"1": "10:00", "2": "10:30"}}
            }
        }
    }
    
    new_state = {
        "Dentist": {
            "doctors": {
                "Dr. Smith": {"tickets": {"2": "10:30", "3": "11:00"}}
            }
        }
    }
    
    new_tix, freed_tix, booked_tix = diff_state(old_state, new_state)
    assert len(new_tix) == 1
    assert new_tix[0]["ticket_id"] == "3"
    
    assert len(booked_tix) == 1
    assert booked_tix[0]["ticket_id"] == "1"
    
    print("Differ tests passed!")

if __name__ == "__main__":
    test_differ()
