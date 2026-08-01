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

  // Mapping for pull-payment refunds
  mapping(address => uint) pendingReturns;
  // Reentrancy mutex
  bool private _locked;

  //Takes in bid, refunding the frontrunner if they are outbid
  function bid() payable {
    require(msg.value > currentBid);

    // Instead of pushing funds to the previous frontrunner (which can revert),
    // record the amount owed so they can withdraw it later (pull pattern).
    if (currentFrontrunner != 0) {
      pendingReturns[currentFrontrunner] += currentBid;
    }

    currentFrontrunner = msg.sender;
    currentBid         = msg.value;
  }

  // Let users withdraw their pending returns (pull pattern).
  function withdraw() public returns (bool) {
    require(!_locked);
    _locked = true;

    uint amount = pendingReturns[msg.sender];
    if (amount > 0) {
      // Set to zero before external call (checks-effects-interactions)
      pendingReturns[msg.sender] = 0;
      // Wrap send in require so failures propagate per rules
      require(msg.sender.send(amount));
    }

    _locked = false;
    return true;
  }
}