/*
 * @source: https://github.com/trailofbits/not-so-smart-contracts/blob/master/denial_of_service/auction.sol
 * @author: -
 * @vulnerable_at_lines: 23
 */

pragma solidity ^0.4.15;

//Auction fixed to prevent DoS attack
contract DosAuction {
  address public currentFrontrunner;
  uint public currentBid;
  mapping(address => uint) public refunds;

  //Takes in bid, refunding the frontrunner if they are outbid
  function bid() payable {
    require(msg.value > currentBid);

    if (currentFrontrunner != 0) {
      refunds[currentFrontrunner] += currentBid;
    }

    currentFrontrunner = msg.sender;
    currentBid         = msg.value;
  }

  function withdraw() public {
    uint amount = refunds[msg.sender];
    refunds[msg.sender] = 0;
    require(msg.sender.send(amount));
  }
}