contract SmartFix {
  address public smartfix_owner = msg.sender;
}

pragma solidity ^0.5.0;

contract Target is SmartFix {

    function bug_unchk_send8() payable public{
          require((smartfix_owner == msg.sender)); /* <FIX> Insert */
          msg.sender.transfer(1 ether);}

    function() external payable {}

    function deposit() public payable {}

}
