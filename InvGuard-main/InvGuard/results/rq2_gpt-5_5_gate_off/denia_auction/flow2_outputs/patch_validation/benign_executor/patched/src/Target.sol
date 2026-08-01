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
  mapping(address => uint) pendingReturns;

  //Takes in bid, recording the frontrunner's refund if they are outbid
  function bid() payable {
    require(msg.value > currentBid);

    if (currentFrontrunner != 0) {
      require(pendingReturns[currentFrontrunner] + currentBid >= pendingReturns[currentFrontrunner]);
      pendingReturns[currentFrontrunner] += currentBid;
    }

    currentFrontrunner = msg.sender;
    currentBid         = msg.value;
  }

  function withdraw() public {
    uint amount = pendingReturns[msg.sender];
    require(amount > 0);

    pendingReturns[msg.sender] = 0;
    require(msg.sender.send(amount));
  }
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `DosAuction` has a no-arg constructor (or implicit constructor).
contract Target is DosAuction {
    constructor() DosAuction() {}
}
