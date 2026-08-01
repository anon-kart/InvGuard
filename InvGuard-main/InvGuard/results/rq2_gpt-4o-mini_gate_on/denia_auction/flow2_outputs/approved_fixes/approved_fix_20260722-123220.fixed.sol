/*
 * @source: https://github.com/trailofbits/not-so-smart-contracts/blob/master/denial_of_service/auction.sol
 * @author: -
 * @vulnerable_at_lines: 23
 */

pragma solidity ^0.4.15;

//Auction converted to pull-payment pattern
contract DosAuction {
  address currentFrontrunner;
  uint currentBid;
  mapping(address => uint) public pendingReturns;

  //Takes in bid, refunding the frontrunner if they are outbid
  function bid() payable {
    require(msg.value > currentBid);

    if (currentFrontrunner != 0) {
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