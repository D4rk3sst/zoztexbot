from zoztex import Quotex
from zoztex.utils.account_type import AccountType
qtx_email = "robert.giovino1944@proton.me"
qtx_pass = "Robert124125126****"
account = (AccountType.PRACTICE)
amount = 2
amount_gale = 4.33
duration = 300  #in seconds

qtx = Quotex(
    qtx_email, 
    qtx_pass, 
    headless=True, websocket_thread = True
    )
