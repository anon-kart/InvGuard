/*
 * @source: https://github.com/trailofbits/not-so-smart-contracts/blob/master/denial_of_service/auction.sol
 * @author: -
 * @vulnerable_at_lines: 23
 */

pragma solidity ^0.4.15;

//Auction susceptible to DoS attack
contract DosAuction {
  address currentFrontrunner;
  uint currentBid;

  // Reentrancy mutex required by patch rules
  bool private _locked;

  // Pull-payment storage for refunds to avoid push-loop DoS
  mapping(address => uint) public pendingReturns;

  //Takes in bid, refunding the frontrunner if they are outbid
  function bid() payable {
    require(msg.value > currentBid);

    // Reentrancy mutex
    require(!_locked);
    _locked = true;

    // Record the refund owed to the previous frontrunner (pull-payment).
    if (currentFrontrunner != 0) {
      // Prevent overflow when adding refunds
      uint prev = currentBid;
      uint newAmount = pendingReturns[currentFrontrunner] + prev;
      require(newAmount >= pendingReturns[currentFrontrunner]);
      pendingReturns[currentFrontrunner] = newAmount;
    }

    // Update state before any external interaction (there are none here).
    currentFrontrunner = msg.sender;
    currentBid         = msg.value;

    _locked = false;
  }

  // Withdraw pattern: allow users to pull their refunds.
  function withdraw() public returns (bool) {
    require(!_locked);
    _locked = true;

    uint amount = pendingReturns[msg.sender];
    require(amount > 0);

    // Effects
    pendingReturns[msg.sender] = 0;

    // Interaction: send funds, require success per rules
    require(msg.sender.send(amount));

    _locked = false;
    return true;
  }
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `DosAuction` has a no-arg constructor (or implicit constructor).
contract Target is DosAuction {
    constructor() DosAuction() {}
}
