pragma solidity ^0.5.11;

contract Target {

    uint receivers_unchk18;
    address payable addr_unchk18;

    function bug_unchk18() public{
    uint receivers_unchk18;
    address payable addr_unchk18;
    if (!addr_unchk18.send(42 ether))
     	{receivers_unchk18 +=1;}
    else
     	{revert();}
    }

    function() external payable {}

    function deposit() public payable {}

}
