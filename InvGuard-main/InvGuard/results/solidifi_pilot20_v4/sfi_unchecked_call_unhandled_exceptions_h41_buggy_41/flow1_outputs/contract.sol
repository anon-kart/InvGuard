pragma solidity >=0.4.22 <0.6.0;

contract Target {
    constructor() public payable {}

    uint receivers_unchk30;
    address payable addr_unchk30;

    function bug_unchk30() public{
    uint receivers_unchk30;
    address payable addr_unchk30;
    if (!addr_unchk30.send(42 ether))
     {receivers_unchk30 +=1;}
    else
     {revert();}
    }

    function() external payable {}

    function deposit() public payable {}

}
